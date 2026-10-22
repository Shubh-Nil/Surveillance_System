import importlib.util,json,pathlib,tempfile,unittest
P=pathlib.Path(__file__).resolve().parents[1]/'orchestrator.py';spec=importlib.util.spec_from_file_location('orch',P);o=importlib.util.module_from_spec(spec);spec.loader.exec_module(o)
class Flow(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.old=o.R;o.R=pathlib.Path(self.tmp.name);self.s={'status':'READY','phase':'assign','attempt':1,'task_id':'TASK-01','seen':[]}
 def tearDown(self):o.R=self.old;self.tmp.cleanup()
 def queue(self,*messages):o.save(o.R/'mock_responses.json',list(messages))
 def assignment(self,a=1):return o.msg('TASK_ASSIGNMENT','TASK-01',a,'PM','TL1','task',objective='audit',approved_inputs=['MOT20'],limits={},acceptance_criteria=['report'],expected_artifacts=['report.md'],branch='TL1')
 def result(self,a=1,evidence=True):
  m=o.msg('TASK_RESULT','TASK-01',a,'TL1','PM','done',status='RESULTS_READY');m['evidence']=['report.md'] if evidence else [];return m
 def review(self,d,a=1):return o.msg('REVIEW_DECISION','TASK-01',a,'PM','TL1','review',decision=d)
 def test_success_and_no_main_write(self):
  head=o.git('rev-parse','main');self.queue(self.assignment(),self.result(),self.review('ACCEPT'));self.assertEqual(o.run(self.s,1,True)['status'],'READY');self.assertEqual(head,o.git('rev-parse','main'));self.assertEqual(len((o.R/'history.jsonl').read_text().splitlines()),3)
 def test_revision(self):
  self.queue(self.assignment(),self.result(),self.review('REVISE'),self.result(2),self.review('ACCEPT',2));self.assertEqual(o.run(self.s,1,True)['status'],'READY')
 def test_blocked(self):
  self.queue(self.assignment(),self.result(),self.review('BLOCKED'));self.assertEqual(o.run(self.s,1,True)['status'],'BLOCKED')
 def test_question_answer(self):
  q=o.msg('SUPERVISOR_QUESTION','TASK-01',1,'PM','SUPERVISOR','choose',question_id='Q1');self.queue(q);self.assertEqual(o.run(self.s,1,True)['status'],'WAITING_FOR_SUPERVISOR');self.assertEqual(self.s['question_id'],'Q1')
 def test_duplicate(self):
  m=self.assignment();self.assertTrue(o.record(self.s,m));self.assertFalse(o.record(self.s,m));self.assertEqual(len((o.R/'history.jsonl').read_text().splitlines()),1)
 def test_interruption(self):
  self.queue(self.assignment());self.assertEqual(o.run(self.s,1,True)['status'],'PAUSED_UNCERTAIN');self.assertIsNotNone(o.read(o.R/'state.json',{})['checkpoint'])
 def test_missing_evidence(self):
  self.queue(self.assignment(),self.result(evidence=False),self.review('ACCEPT'));self.assertEqual(o.run(self.s,1,True)['status'],'BLOCKED')
 def test_schema_and_limits(self):
  with self.assertRaises(ValueError):o.valid({'type':'TASK_RESULT'})
  with self.assertRaises(ValueError):o.run(self.s,3,True)
 def test_runtime_ignored(self):self.assertEqual(o.git('check-ignore','.agents/runtime/state.json'),'.agents/runtime/state.json')
if __name__=='__main__':unittest.main()
