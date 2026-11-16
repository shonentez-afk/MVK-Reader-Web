"""Read-only MCP stdio JSON-RPC 2.0 server for the user-supplied MVK IDR KB.

It exposes NO execution, click, process attach, remote code, network, or write tools.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import sqlite3
import sys

ADDRESS=re.compile(r'^(?:0x)?([0-9a-fA-F]{8})$')


def norm_address(s):
    m=ADDRESS.fullmatch(str(s).strip())
    if not m:raise ValueError('Address must be 8 hex digits (optionally 0x-prefixed)')
    return m.group(1).upper()


def limit_value(v,maximum=100):return max(1,min(maximum,int(v)))


class IDRService:
    def __init__(self,db:Path,sources:Path|None=None):
        if not db.is_file():raise FileNotFoundError(db)
        self.db=db.resolve()
        self.sources=sources.resolve() if sources else None
        self.c=sqlite3.connect('file:'+str(self.db).replace('\\','/')+'?mode=ro',uri=True)
        self.c.row_factory=sqlite3.Row
        if not self.c.execute("SELECT 1 FROM sqlite_master WHERE name='functions'").fetchone():
            raise ValueError('Database is not MVK IDR Bridge')

    def rows(self,sql,args=(),limit=100):
        return [dict(r) for r in self.c.execute(sql+' LIMIT ?',tuple(args)+(limit,)).fetchall()]

    def stats(self):
        counts={table:self.c.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
                for table in ['source_files','functions','calls','forms','components','events']}
        counts['linked_events']=self.c.execute('SELECT COUNT(*) FROM events WHERE handler_address IS NOT NULL').fetchone()[0]
        counts['linked_calls']=self.c.execute('SELECT COUNT(*) FROM calls WHERE resolved_address IS NOT NULL').fetchone()[0]
        return {'counts':counts,'idp':json.loads(self.c.execute("SELECT value FROM meta WHERE key='idp_header'").fetchone()[0]),
                'read_only':True,'hardware_actions_available':False}

    def search(self,query:str,limit:int=25):
        q='%'+query.strip()[:150].replace('%','\\%').replace('_','\\_')+'%'
        lim=limit_value(limit,50)
        return {'query':query,'functions':self.rows("SELECT address,name,kind,unit,source_file,line FROM functions WHERE name LIKE ? ESCAPE '\\' ORDER BY CASE WHEN name LIKE ? ESCAPE '\\' THEN 0 ELSE 1 END, name",(q,q),lim),
                'components':self.rows("SELECT path,form_name,component_name,class_name,caption FROM components WHERE component_name LIKE ? ESCAPE '\\' OR caption LIKE ? ESCAPE '\\' ORDER BY form_name,path",(q,q),lim),
                'events':self.rows("SELECT component_path,event_name,handler_name,handler_address,resolution FROM events WHERE handler_name LIKE ? ESCAPE '\\'",(q,),lim)}

    def function(self,address:str,limit:int=35):
        a=norm_address(address);lim=limit_value(limit,75)
        rec=self.c.execute('SELECT * FROM functions WHERE address=?',(a,)).fetchone()
        if rec is None:return {'address':a,'found':False}
        return {'found':True,'function':dict(rec),
                'outgoing_calls':self.rows('SELECT site_address,raw_target,target_name,target_address,resolved_address,source_file,line FROM calls WHERE caller_address=? ORDER BY site_address',(a,),lim),
                'incoming_calls':self.rows('SELECT caller_address,site_address,raw_target,source_file,line FROM calls WHERE resolved_address=? ORDER BY site_address',(a,),lim),
                'truncated':(self.c.execute('SELECT COUNT(*) FROM calls WHERE caller_address=?',(a,)).fetchone()[0] > lim)}

    def forms(self,form:str|None=None,limit:int=100):
        if not form:return {'forms':self.rows('SELECT * FROM forms ORDER BY name',(),limit_value(limit))}
        lim=limit_value(limit,500)
        header=self.c.execute('SELECT * FROM forms WHERE name=? COLLATE NOCASE',(form,)).fetchone()
        if not header:return {'found':False,'form':form}
        return {'found':True,'form':dict(header),
                'components':self.rows('SELECT path,component_name,class_name,parent_path,caption,caption_raw,properties_json,source_file,line FROM components WHERE form_name=? ORDER BY path',(header['name'],),lim),
                'events':self.rows('SELECT component_path,event_name,handler_name,handler_address,resolution,source_file,line FROM events WHERE form_name=? ORDER BY component_path',(header['name'],),lim)}

    def component(self,name:str,limit:int=25):
        q='%'+str(name).strip()[:150]+'%'
        matches=self.rows('SELECT * FROM components WHERE component_name LIKE ? OR path LIKE ? ORDER BY form_name,path',(q,q),limit_value(limit,100))
        for row in matches:
            row['properties']=json.loads(row.pop('properties_json'))
            row['events']=self.rows('SELECT event_name,handler_name,handler_address,resolution,source_file,line FROM events WHERE component_path=?',(row['path'],),100)
        return {'query':name,'matches':matches}

    def event_chain(self,component_name:str,depth:int=2,max_nodes:int=100):
        # The graph is STATIC. Never treat an event association as a runtime execution trace.
        components=self.component(component_name,25)['matches']
        chains=[]
        for c in components:
            for e in c['events']:
                if e['handler_address']:
                    graph=self.trace(e['handler_address'],depth=depth,max_nodes=max_nodes)
                    chains.append({'component_path':c['path'],'event':e,'static_call_graph':graph})
        return {'query':component_name,'chains':chains,'source':'reconstructed_DFM_and_PAS','runtime_verified':False}

    def trace(self,address:str,depth:int=2,max_nodes:int=100):
        start=norm_address(address);depth=max(0,min(4,int(depth)));max_nodes=limit_value(max_nodes,250)
        seen=set();nodes=[];edges=[];frontier=[(start,0)]
        while frontier and len(seen)<max_nodes:
            addr,d=frontier.pop(0)
            if addr in seen:continue
            f=self.c.execute('SELECT address,name,unit,source_file,line FROM functions WHERE address=?',(addr,)).fetchone()
            if f is None:continue
            nodes.append(dict(f));seen.add(addr)
            if d>=depth:continue
            for r in self.c.execute('SELECT site_address,raw_target,resolved_address,source_file,line FROM calls WHERE caller_address=? ORDER BY site_address',(addr,)):
                edges.append({'caller':addr,'site':r['site_address'],'target':r['raw_target'],
                              'resolved_address':r['resolved_address'],'evidence':f"{r['source_file']}:{r['line']}"})
                if r['resolved_address'] and r['resolved_address'] not in seen:
                    frontier.append((r['resolved_address'],d+1))
                if len(edges)>=max_nodes*12:break
        return {'start':start,'depth':depth,'nodes':nodes,'edges':edges,'max_nodes':max_nodes,
                'partial':bool(frontier),'analysis':'static_disassembly_only'}

    def callers(self,address:str,limit:int=100):
        a=norm_address(address)
        return {'address':a,'callers':self.rows('SELECT c.caller_address,f.name,c.site_address,c.raw_target,c.source_file,c.line FROM calls c LEFT JOIN functions f ON f.address=c.caller_address WHERE c.resolved_address=? ORDER BY c.site_address',(a,),limit_value(limit))}

    def code(self,address:str,lines:int=60):
        a=norm_address(address)
        f=self.c.execute('SELECT * FROM functions WHERE address=?',(a,)).fetchone()
        if f is None:return {'address':a,'found':False}
        file=f['source_file'];from_line=f['line'];n=limit_value(lines,200)
        if self.sources is None:return {'function':dict(f),'code_unavailable':'Pass --sources directory with exported PAS files'}
        real=(self.sources/file).resolve()
        if not real.is_relative_to(self.sources):raise ValueError('Invalid path in database')
        if not real.is_file():return {'function':dict(f),'code_unavailable':f'Source not found: {file}'}
        body=real.read_bytes().decode('cp1252',errors='replace').split('\n')
        start=max(0,from_line-2);end=min(len(body),start+n,f['end_line'])
        return {'function':dict(f),'code':[{'line':i+1,'text':body[i][:500]} for i in range(start,end)],
                'truncated':end<f['end_line'],'source_kind':'IDR_reconstructed_PAS'}


TOOL_DEFS=[
 ('idr_stats','Read corpus metadata, coverage, and IDP header',{}),
 ('idr_search','Find reconstructed Delphi methods, DFM controls and handlers by text',{'query':{'type':'string'},'limit':{'type':'integer','minimum':1,'maximum':50}}),
 ('idr_function','Inspect static function metadata and incoming/outgoing calls',{'address':{'type':'string'},'limit':{'type':'integer','minimum':1,'maximum':75}}),
 ('idr_forms','List forms or return a form and its DFM components',{'form':{'type':'string'},'limit':{'type':'integer','minimum':1,'maximum':500}}),
 ('idr_component','Find DFM component properties and its event handlers',{'name':{'type':'string'},'limit':{'type':'integer','minimum':1,'maximum':100}}),
 ('idr_event_chain','Trace static component -> Delphi handler -> bounded call graph',{'component_name':{'type':'string'},'depth':{'type':'integer','minimum':0,'maximum':4},'max_nodes':{'type':'integer','minimum':1,'maximum':250}}),
 ('idr_trace','Bounded static direct-call graph by function address',{'address':{'type':'string'},'depth':{'type':'integer','minimum':0,'maximum':4},'max_nodes':{'type':'integer','minimum':1,'maximum':250}}),
 ('idr_callers','List reconstructed static callers of an address',{'address':{'type':'string'},'limit':{'type':'integer','minimum':1,'maximum':100}}),
 ('idr_code','Read reconstructed listing of a specific method if sources configured',{'address':{'type':'string'},'lines':{'type':'integer','minimum':1,'maximum':200}}),
]
REQUIRED={'idr_search':['query'],'idr_function':['address'],'idr_component':['name'],
          'idr_event_chain':['component_name'],'idr_trace':['address'],'idr_callers':['address'],'idr_code':['address']}

def tool_specs():
    return [{'name':name,'description':desc,'inputSchema':{'type':'object','properties':props,'required':REQUIRED.get(name,[]),'additionalProperties':False}} for name,desc,props in TOOL_DEFS]


def dispatch(service:IDRService,method:str,params:dict):
    if method=='initialize':
        return {'protocolVersion':'2024-11-05','capabilities':{'tools':{}},
                'serverInfo':{'name':'mvk-idr-readonly','version':'1.0.0'}}
    if method=='ping':return {}
    if method=='tools/list':return {'tools':tool_specs()}
    if method=='tools/call':
        name=params.get('name'); args=params.get('arguments') or {}
        if name=='idr_stats':answer=service.stats()
        elif name=='idr_search':answer=service.search(**args)
        elif name=='idr_function':answer=service.function(**args)
        elif name=='idr_forms':answer=service.forms(**args)
        elif name=='idr_component':answer=service.component(**args)
        elif name=='idr_event_chain':answer=service.event_chain(**args)
        elif name=='idr_trace':answer=service.trace(**args)
        elif name=='idr_callers':answer=service.callers(**args)
        elif name=='idr_code':answer=service.code(**args)
        else:raise ValueError('Unknown tool: '+str(name))
        return {'content':[{'type':'text','text':json.dumps(answer,ensure_ascii=False,default=str)}],'isError':False}
    raise ValueError('Unsupported JSON-RPC method: '+str(method))


def serve(service):
    for line in sys.stdin.buffer:
        try:
            request=json.loads(line.decode('utf-8'))
            if not isinstance(request,dict):continue
            if request.get('method','').startswith('notifications/'):
                continue
            if 'id' not in request:continue
            try:
                result=dispatch(service,request.get('method'),request.get('params') or {})
                response={'jsonrpc':'2.0','id':request['id'],'result':result}
            except Exception as exc:
                response={'jsonrpc':'2.0','id':request['id'],'error':{'code':-32602,'message':f'{type(exc).__name__}: {exc}'}}
            sys.stdout.write(json.dumps(response,ensure_ascii=False,separators=(',',':'))+'\n')
            sys.stdout.flush()
        except Exception as exc:
            print(f'MCP transport parse error: {exc}',file=sys.stderr,flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db',type=Path,required=True)
    p.add_argument('--sources',type=Path,help='Optional directory containing reconstructed PAS files')
    a=p.parse_args();serve(IDRService(a.db,a.sources))

if __name__=='__main__':main()