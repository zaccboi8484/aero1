import pathlib
import subprocess
import tempfile
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
HELPER=ROOT/"scripts/retry_evidence_push.sh"

def cmd(cwd,*args,check=True):
    return subprocess.run(args,cwd=cwd,check=check,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
def commit(cwd,name,value):
    (cwd/name).write_text(value,encoding="utf-8")
    cmd(cwd,"git","add",name)
    cmd(cwd,"git","commit","-m","source update")

class EvidencePushTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=pathlib.Path(self.temp.name)
        self.remote=self.root/"remote.git"
        cmd(self.root,"git","init","--bare","--initial-branch=main",str(self.remote))
        self.a=self.root/"a"
        self.b=self.root/"b"
        cmd(self.root,"git","clone",str(self.remote),str(self.a))
        self.configure(self.a)
        commit(self.a,"seed.txt","reference data preserved\n")
        cmd(self.a,"git","push","origin","HEAD:main")
        cmd(self.root,"git","clone",str(self.remote),str(self.b))
        self.configure(self.b)
    def configure(self,d):
        cmd(d,"git","config","user.email","gatekeeper-test@example.invalid")
        cmd(d,"git","config","user.name","GateKeeper test")
    def test_nonoverlapping_evidence_writes_survive_competing_pushes(self):
        commit(self.a,"alpha.json",'{"author":"collector-A"}\n')
        commit(self.b,"beta.json",'{"author":"collector-B"}\n')
        cmd(self.a,"git","push","origin","HEAD:main")
        pushed=cmd(self.b,"bash",str(HELPER))
        self.assertIn("published evidence safely",pushed.stdout)
        cmd(self.a,"git","pull","--rebase","origin","main")
        self.assertEqual((self.a/"alpha.json").read_text(),'{"author":"collector-A"}\n')
        self.assertEqual((self.a/"beta.json").read_text(),'{"author":"collector-B"}\n')
    def test_conflicting_evidence_never_force_overwritten(self):
        commit(self.a,"seed.txt","A authoritative source write\n")
        commit(self.b,"seed.txt","B competing different write\n")
        cmd(self.a,"git","push","origin","HEAD:main")
        refused=cmd(self.b,"bash",str(HELPER),check=False)
        self.assertEqual(refused.returncode,3)
        self.assertIn("source conflict",refused.stderr)
        cmd(self.b,"git","fetch","origin","main")
        upstream=cmd(self.b,"git","show","origin/main:seed.txt")
        self.assertEqual(upstream.stdout,"A authoritative source write\n")

if __name__=="__main__":
    unittest.main()
