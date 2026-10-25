import json,socket,struct,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import patch
from collector.core import Collector,modbus_read,ProtocolError

class MockServer:
    def __init__(self):
        self.s=socket.socket();self.s.bind(('127.0.0.1',0));self.s.listen(1);self.port=self.s.getsockname()[1];self.packet=None
        self.t=threading.Thread(target=self.run,daemon=True);self.t.start()
    def run(self):
        try:
            c,_=self.s.accept()
            with c:
                self.packet=c.recv(1024)
                tid,_,_,unit,fun,adr,count=struct.unpack('>HHHBBHH',self.packet)
                data=struct.pack('>'+('H'*count),*list(range(100,100+count)))
                pdu=bytes([3,len(data)])+data
                c.sendall(struct.pack('>HHHB',tid,0,len(pdu)+1,unit)+pdu)
        finally:self.s.close()

class CollectorTests(unittest.TestCase):
    def test_fc03_only(self):
        sim=MockServer();r=modbus_read('127.0.0.1',sim.port,0x1000,2);sim.t.join(2)
        self.assertEqual(r,[100,101]);self.assertEqual(sim.packet[7],3)
    def test_sql_history_and_live(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td);sim=MockServer()
            config={'devices':[{'id':'d1','number':'44','ip':'127.0.0.1','port':sim.port,'enabled':True,'read_ranges':[{'address':4096,'count':2}],'interval_seconds':None}]}
            (path/'devices.json').write_text(json.dumps(config))
            c=Collector(path/'devices.json',path/'d.sqlite3')
            self.assertEqual(c.public_devices()[0]['status'],'not_polled')
            self.assertEqual(c.poll_once('d1')['ranges'][0]['values'],[100,101])
            self.assertEqual(c.history('d1')[0]['values'],[100,101]);sim.t.join(2)
    def test_no_unconfigured_poll(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td);(path/'cfg.json').write_text(json.dumps({'devices':[{'id':'d','ip':'127.0.0.1','port':502,'enabled':False,'read_ranges':[],'interval_seconds':None}]}))
            c=Collector(path/'cfg.json',path/'db.sqlite3')
            with self.assertRaises(ValueError):c.poll_once('d')
    def test_invalid_range(self):
        with self.assertRaises(ValueError):modbus_read('127.0.0.1',502,65535,2)

if __name__=='__main__':unittest.main()
