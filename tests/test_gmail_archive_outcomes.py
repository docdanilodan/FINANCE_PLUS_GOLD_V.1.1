import importlib.util,sys,types,unittest,os,io,json
from unittest.mock import patch
from contextlib import redirect_stdout
from pathlib import Path
pipeline=types.ModuleType('services.gmail_drive_pipeline');pipeline.sync_gmail_attachments=lambda **kw:{'errors':[]}
auth=types.ModuleType('services.google_auth');auth.discover_google_profiles=lambda:['DEFAULT'];auth.token_env_name=lambda p:'GOOGLE_OAUTH_TOKEN_JSON'
spec=importlib.util.spec_from_file_location('archive',Path(__file__).resolve().parents[1]/'scripts'/'sync_gmail_archive.py');mod=importlib.util.module_from_spec(spec);
with patch.dict(sys.modules,{'services':types.ModuleType('services'),'services.gmail_drive_pipeline':pipeline,'services.google_auth':auth}):spec.loader.exec_module(mod)
class Test(unittest.TestCase):
 def run_case(self,result=None,env=None,exc=None):
  cfg={'AIRTABLE_TOKEN':'fixture','AIRTABLE_BASE_ID':'fixture','GOOGLE_OAUTH_TOKEN_JSON':'fixture','GOOGLE_DRIVE_FOLDER_ID':'fixture'} if env is None else env
  out=io.StringIO()
  with patch.dict(os.environ,cfg,clear=True),patch.object(mod,'sync_gmail_attachments',return_value=result,side_effect=exc),redirect_stdout(out):code=mod.main()
  return code,out.getvalue()
 def test_success(self):self.assertEqual(self.run_case({'errors':[]})[0],0)
 def test_partial_failure(self):
  code,out=self.run_case({'errors':[{'message_id':'PRIVATE','error':'SECRET'}]});self.assertEqual(code,1);self.assertNotIn('ARCHIVE_OK',out);self.assertNotIn('PRIVATE',out);self.assertNotIn('SECRET',out)
 def test_exception_sanitized(self):
  code,out=self.run_case(exc=RuntimeError('SECRET'));self.assertEqual(code,1);self.assertNotIn('SECRET',out)
 def test_config_blocked(self):self.assertEqual(self.run_case(env={})[0],2)
 def test_invalid_result(self):self.assertEqual(self.run_case(None)[0],1)
 def test_email_redacted(self):self.assertNotIn('PRIVATE',self.run_case({'errors':[],'source_email':'PRIVATE'})[1])
if __name__=='__main__':unittest.main(verbosity=2)
