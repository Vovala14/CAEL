"""Isolated parsers/decoders with wall-time and Windows process-tree memory caps."""
import base64
import json
import os
import subprocess
import sys
from pathlib import Path

from .workspace import ToolError


class ProcessJob:
    def __init__(self,process,megabytes=768):
        self.handle=None
        if os.name!='nt':return
        import ctypes
        from ctypes import wintypes as w
        size=ctypes.c_size_t
        class Basic(ctypes.Structure):
            _fields_=[('process_time',ctypes.c_int64),('job_time',ctypes.c_int64),('flags',w.DWORD),
                      ('minimum',size),('maximum',size),('active',w.DWORD),('affinity',size),('priority',w.DWORD),('scheduling',w.DWORD)]
        class Counters(ctypes.Structure):_fields_=[(name,ctypes.c_uint64) for name in ('read_ops','write_ops','other_ops','read_bytes','write_bytes','other_bytes')]
        class Extended(ctypes.Structure):_fields_=[('basic',Basic),('io',Counters),('process_memory',size),('job_memory',size),('peak_process',size),('peak_job',size)]
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.CreateJobObjectW.argtypes=[ctypes.c_void_p,w.LPCWSTR];kernel.CreateJobObjectW.restype=w.HANDLE
        kernel.SetInformationJobObject.argtypes=[w.HANDLE,ctypes.c_int,ctypes.c_void_p,w.DWORD];kernel.SetInformationJobObject.restype=w.BOOL
        kernel.AssignProcessToJobObject.argtypes=[w.HANDLE,w.HANDLE];kernel.AssignProcessToJobObject.restype=w.BOOL
        kernel.CloseHandle.argtypes=[w.HANDLE];kernel.CloseHandle.restype=w.BOOL
        self.kernel=kernel;handle=kernel.CreateJobObjectW(None,None)
        if not handle:raise ToolError('Cannot create parser resource job')
        settings=Extended();settings.basic.flags=0x2000|0x200  # Kill-on-close, total job memory.
        settings.job_memory=megabytes*1024*1024
        if not kernel.SetInformationJobObject(handle,9,ctypes.byref(settings),ctypes.sizeof(settings)) or not kernel.AssignProcessToJobObject(handle,int(process._handle)):
            kernel.CloseHandle(handle);raise ToolError('Cannot enforce parser process-tree resource boundary')
        self.handle=handle

    def close(self):
        if self.handle:self.kernel.CloseHandle(self.handle);self.handle=None


def analyze(kind,blob,options,timeout=25):
    if kind not in {'pdf','image','video'}:raise ToolError('Unknown local analysis operation')
    if len(blob)>50_000_000:raise ToolError('Parser input byte limit')
    flags=getattr(subprocess,'CREATE_NO_WINDOW',0)
    process=subprocess.Popen([sys.executable,'-m','cael_unified.local_tools.worker'],cwd=Path(__file__).resolve().parents[2],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=flags)
    job=None
    try:
        job=ProcessJob(process,2048 if kind=='video' else 768)
        payload=json.dumps(dict(kind=kind,blob=base64.b64encode(blob).decode('ascii'),options=options)).encode()
        stdout,stderr=process.communicate(payload,timeout=timeout)
        if process.returncode:raise ToolError('Parser/decoder failed or exceeded its resource boundary')
        if len(stdout)>2_000_000:raise ToolError('Parser output byte limit')
        result=json.loads(stdout)
        if result.get('status')=='error':raise ToolError(result['error'])
        return result
    except subprocess.TimeoutExpired:
        if job:job.close()
        process.kill();process.communicate();raise ToolError('Parser/decoder timed out; content remains unreviewed')
    finally:
        if process.poll() is None:process.kill();process.communicate()
        if job:job.close()
