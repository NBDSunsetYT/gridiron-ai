"""Local audit-only snapshot fencing. Never opens application user databases."""
from contextlib import contextmanager
from pathlib import Path
import fcntl,os,uuid

@contextmanager
def snapshot_claim(path):
 handle=Path(str(path)+'.lock').open('a+b');claimed=False
 try:
  try:fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB);claimed=True
  except BlockingIOError:pass
  yield claimed
 finally:
  if claimed:fcntl.flock(handle,fcntl.LOCK_UN)
  handle.close()

def write_snapshot_once(path,raw):
 """An interrupted write cannot expose partial data or replace a prior run."""
 path=Path(path);temporary=path.with_name(path.name+'.partial-'+uuid.uuid4().hex)
 try:
  with temporary.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
  try:os.link(temporary,path);return True
  except FileExistsError:return False
 finally:temporary.unlink(missing_ok=True)
