#!/usr/bin/env python3
from jsonschema import Draft202012Validator, FormatChecker, ValidationError
import argparse,datetime,fcntl,json,os,pathlib,subprocess,tempfile,uuid
ROOT=pathlib.Path(__file__).resolve().parents[1]; CFG=json.loads((ROOT/'.agents/config.json').read_text()); R=ROOT/CFG['runtime_path']
def save(p,v):
 p.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.NamedTemporaryFile('w',dir=p.parent,delete=False) as f: json.dump(v,f,indent=2);f.flush();os.fsync(f.fileno());n=f.name
 os.replace(n,p)
def read(p,d): return json.loads(p.read_text()) if p.exists() else d
def msg(t,task,attempt,source,recipient,summary,**kw): return dict(schema_version='1.0',message_id=str(uuid.uuid4()),task_id=task,attempt=attempt,source=source,recipient=recipient,type=t,timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),summary=summary,evidence=[],**kw)
def valid(m):
 try:
  schema=json.loads((ROOT/'.agents/protocol.schema.json').read_text())
  Draft202012Validator.check_schema(schema)
  Draft202012Validator(schema,format_checker=FormatChecker()).validate(m)
 except ValidationError as exc: raise ValueError(str(exc)) from exc
 return m

def record(s,m):
 valid(m)
 if m['message_id'] in s['seen']: return False
 with (R/'history.jsonl').open('a') as f:f.write(json.dumps(m)+'\n');f.flush();os.fsync(f.fileno())
 s['seen'].append(m['message_id']);save(R/'state.json',s);return True
def git(*a):return subprocess.check_output(['git','-C',str(ROOT),*a],text=True).strip()
class Limit(Exception):pass
def invoke(role,packet,mock):
 if mock:
  p=R/'mock_responses.json';q=read(p,[])
  if not q:raise RuntimeError('mock queue empty')
  m=q.pop(0);save(p,q);return valid(m)
 if not CFG['live_execution_enabled']:raise RuntimeError('live disabled')
 key='pm' if role=='PM' else 'tl'
 path=CFG.get(key+'_prompt_path')
 if not path or not pathlib.Path(path).is_file():raise RuntimeError('missing role prompt')
 out=R/('response-'+role+'.json');cmd=[CFG['codex_command'],'exec','--ephemeral','--sandbox','read-only' if role=='PM' else 'workspace-write','-C',str(ROOT),'--output-schema',str(ROOT/'.agents/protocol.schema.json'),'-o',str(out)]
 if CFG.get(key+'_model'):cmd+=['--model',CFG[key+'_model']]
 cmd+=['-c','model_reasoning_effort="'+CFG[key+'_effort']+'"','-']
 try:p=subprocess.run(cmd,input=pathlib.Path(path).read_text()+'\nReturn one JSON message. Packet:\n'+json.dumps(packet),text=True,capture_output=True,timeout=CFG['timeout_seconds'])
 except subprocess.TimeoutExpired:raise RuntimeError('timeout; uncertain outcome')
 if p.returncode:
  if 'usage limit' in p.stderr.lower() or 'rate limit' in p.stderr.lower():raise Limit()
  raise RuntimeError('CLI failure; uncertain outcome')
 return valid(json.loads(out.read_text()))
def run(s,n,mock):
 if not mock and not CFG.get('live_execution_enabled'): raise RuntimeError('live execution disabled')
 if git('branch','--show-current')!='TL1':raise RuntimeError('TL1 required')
 if n<1 or n>CFG['max_tasks_per_batch']:raise ValueError('batch limit')
 if s['status'] not in {'READY','PAUSED'}:raise RuntimeError('reconcile current state first')
 for _ in range(n):
  task=s.get('task_id') or 'TASK-01';packet={'task_id':task,'attempt':s['attempt'],'prior':s.get('last_message')}
  while True:
   phase=s['phase'];role='PM' if phase in {'assign','review'} else 'TL1';attempt=s['attempt']
   s.update(status='INVOKING',checkpoint={'role':role,'phase':phase,'task_id':task,'attempt':attempt,'branch':'TL1','commit':git('rev-parse','HEAD'),'started_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'expected_output':str(R/('response-'+role+'.json'))});save(R/'state.json',s)
   try:
    m=invoke(role,packet,mock)
    if m['task_id']!=task or m['attempt']!=attempt or m['source']!=role or m['type'] not in {'assign':{'TASK_ASSIGNMENT','SUPERVISOR_QUESTION','ERROR_REPORT'},'execute':{'TASK_RESULT','ERROR_REPORT'},'review':{'REVIEW_DECISION','SUPERVISOR_QUESTION','ERROR_REPORT'}}[phase]:raise ValueError('unexpected response')
    if not record(s,m): raise ValueError('duplicate response; reconciliation required')
    s['last_message']=m;s['checkpoint']=None
    if m['type']=='SUPERVISOR_QUESTION' or m.get('decision')=='ASK_SUPERVISOR':s.update(status='WAITING_FOR_SUPERVISOR',question_id=m.get('question_id',m['message_id']))
    elif m['type']=='ERROR_REPORT' or m.get('decision')=='BLOCKED' or m.get('status') in {'BLOCKED','FAILED'}:s['status']='BLOCKED'
    elif phase=='assign':s.update(status='ASSIGNED',phase='execute')
    elif phase=='execute':
     s['result_evidence']=m['evidence']
     if m.get('status') in {'SUBMITTED','RUNNING'}:s['status']='PENDING_JOB'
     else:s.update(status='RESULTS_READY',phase='review')
    elif m['decision']=='REVISE':
     if attempt>=CFG['max_attempts_per_task']:s['status']='MAX_ATTEMPTS'
     else:s.update(status='REVISE',phase='execute',attempt=attempt+1)
    elif m['decision']=='ACCEPT':
     if not s.get('result_evidence') and not m['evidence']:s['status']='BLOCKED'
     else:s.update(status='ACCEPTED',phase='assign',attempt=1,task_id=None)
    save(R/'state.json',s);(R/'summary.md').write_text('# Supervisor status\n\n'+s['status']+': '+m['summary']+'\n')
    if s['status'] in {'WAITING_FOR_SUPERVISOR','BLOCKED','PENDING_JOB','MAX_ATTEMPTS','ACCEPTED'}:break
    packet={'task_id':task,'attempt':s['attempt'],'prior':m}
   except Limit:s['status']='PAUSED_USAGE_LIMIT';save(R/'state.json',s);break
   except (RuntimeError,ValueError,OSError) as e:s.update(status='PAUSED_UNCERTAIN',error=str(e));save(R/'state.json',s);break
  if s['status']!='ACCEPTED':break
  s['status']='READY';save(R/'state.json',s)
 return s
def main():
 p=argparse.ArgumentParser();a=p.add_subparsers(dest='command')
 for x in ('status','mock-test','stop','resume'):a.add_parser(x)
 x=a.add_parser('run');x.add_argument('--max-tasks',type=int,default=1);x.add_argument('--mock',action='store_true')
 x=a.add_parser('answer-supervisor');x.add_argument('question_id');x.add_argument('response');o=p.parse_args();R.mkdir(parents=True,exist_ok=True)
 with (R/'lock').open('w') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);s=read(R/'state.json',{'status':'READY','phase':'assign','attempt':1,'task_id':'TASK-01','seen':[]})
  if o.command=='status':print(json.dumps(s,indent=2))
  elif o.command=='mock-test':
   import unittest
   result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover(str(ROOT/'.agents/tests')))
   if not result.wasSuccessful():raise SystemExit(1)
  elif o.command=='stop':s['status']='HALTED';save(R/'state.json',s)
  elif o.command=='resume':print('Inspect checkpoint, output, branch, commit and jobs before retry:',s['status'])
  elif o.command=='answer-supervisor':
   if s['status']!='WAITING_FOR_SUPERVISOR' or o.question_id!=s.get('question_id'):raise SystemExit('question mismatch')
   m=msg('SUPERVISOR_DECISION',s['task_id'],s['attempt'],'SUPERVISOR','PM','Supervisor answered',question_id=o.question_id,response=o.response);record(s,m);s.update(status='PAUSED',last_message=m);save(R/'state.json',s)
  elif o.command=='run':print(json.dumps(run(s,o.max_tasks,o.mock),indent=2))
if __name__=='__main__':main()
