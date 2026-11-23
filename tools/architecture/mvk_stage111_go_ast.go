// Read-only Go AST call graph for MVKView Compatible Stage111 native receiver.
// Static edges are not proofs of a runtime or physical device session.
package main

import (
 "encoding/json"
 "flag"
 "fmt"
 "go/ast"
 "go/parser"
 "go/token"
 "os"
 "path/filepath"
 "sort"
 "strings"
)
const dir="tools/research/native_tcp10230_stage108_live_recording_r6_1/source"
const baseURL="https://github.com/shonentez-afk/MVK-Reader-Web/blob/"
type decl struct { id,name,path,recv,recvVar string; body *ast.BlockStmt }
func receiver(e ast.Expr) string {
 switch x:=e.(type) {
 case *ast.Ident:return x.Name
 case *ast.StarExpr:return receiver(x.X)
 case *ast.IndexExpr:return receiver(x.X)
 default:return ""
 }
}
func count(fl *ast.FieldList) int {
 if fl==nil{return 0}
 n:=0;for _,x:=range fl.List{if len(x.Names)==0{n++}else{n+=len(x.Names)}};return n
}
func analyze(root,sha string)(map[string]any,error){
 entries,err:=os.ReadDir(filepath.Join(root,filepath.FromSlash(dir)));if err!=nil{return nil,err}
 fset:=token.NewFileSet();files:=map[string]*ast.File{};rels:=[]string{}
 for _,ent:=range entries {
  if ent.IsDir()||!strings.HasSuffix(ent.Name(),".go")||strings.HasSuffix(ent.Name(),"_test.go"){continue}
  rel:=filepath.ToSlash(filepath.Join(dir,ent.Name()))
  f,err:=parser.ParseFile(fset,filepath.Join(root,rel),nil,parser.ParseComments|parser.AllErrors)
  if err!=nil{return nil,fmt.Errorf("%s: %w",rel,err)}
  files[rel]=f;rels=append(rels,rel)
 }
 sort.Strings(rels);if len(rels)==0{return nil,fmt.Errorf("no Stage111 Go source files")}
 nodes:=[]map[string]any{};edges:=[]map[string]any{};decls:=[]decl{}
 names:=map[string][]string{};types:=map[string][]string{}
 add:=func(id,typ,name,path string,line int,extra map[string]any){
  n:=map[string]any{"id":id,"type":typ,"name":name,"path":path,"line":line,"group":"Go native R6.1","url":baseURL+sha+"/"+path+fmt.Sprintf("#L%d",line)}
  for k,v:=range extra{n[k]=v};nodes=append(nodes,n)
 }
 link:=func(a,b,typ string,line int,proof string){edges=append(edges,map[string]any{"from":a,"to":b,"type":typ,"line":line,"evidence":proof})}
 for _,path:=range rels{
  f:=files[path];fid:="file:"+path;add(fid,"file",filepath.Base(path),path,1,nil)
  for _,d:=range f.Decls {
   if g,ok:=d.(*ast.GenDecl);ok&&g.Tok==token.TYPE{
    for _,spec:=range g.Specs{
     t,ok:=spec.(*ast.TypeSpec);if !ok{continue}
     name:=t.Name.Name;id:="class:"+path+"::"+name;line:=fset.Position(t.Pos()).Line
     add(id,"class",name,path,line,nil);types[name]=append(types[name],id)
     link(fid,id,"contains",line,"Go AST type declaration")
    }
   }
   fn,ok:=d.(*ast.FuncDecl);if !ok{continue}
   recv,recvVar:="","";if fn.Recv!=nil&&len(fn.Recv.List)>0{
    r:=fn.Recv.List[0];recv=receiver(r.Type);if len(r.Names)>0{recvVar=r.Names[0].Name}
   }
   name:=fn.Name.Name;if recv!=""{name=recv+"."+name}
   id:="function:"+path+"::"+name;line:=fset.Position(fn.Pos()).Line
   add(id,"function",name,path,line,map[string]any{"receiver":recv,"parameters":count(fn.Type.Params),"results":count(fn.Type.Results)})
   names[name]=append(names[name],id)
   decls=append(decls,decl{id:id,name:name,path:path,recv:recv,recvVar:recvVar,body:fn.Body})
   link(fid,id,"contains",line,"Go AST function declaration")
  }
 }
 for _,d:=range decls {if len(types[d.recv])==1{link(types[d.recv][0],d.id,"method-of",0,"Go AST receiver")}}
 direct,unknown,ambiguous:=0,0,0
 for _,d:=range decls {
  if d.body==nil{continue}
  ast.Inspect(d.body,func(n ast.Node)bool{
   call,ok:=n.(*ast.CallExpr);if !ok{return true}
   name,proof:="",""
   switch f:=call.Fun.(type){
   case *ast.Ident:name=f.Name;proof="Go AST direct package call"
   case *ast.SelectorExpr:
    if v,ok:=f.X.(*ast.Ident);ok&&v.Name==d.recvVar&&d.recv!=""{
     name=d.recv+"."+f.Sel.Name;proof="Go AST receiver method call"
    }
   }
   if name==""{unknown++;return true}
   targets:=names[name];if len(targets)==1{
    link(d.id,targets[0],"call-site",fset.Position(call.Pos()).Line,proof+"; static, not runtime");direct++
   }else if len(targets)>1{ambiguous++}else{unknown++}
   return true
  })
 }
 sort.Slice(nodes,func(i,j int)bool{return nodes[i]["id"].(string)<nodes[j]["id"].(string)})
 counts:=map[string]int{"files_scanned":len(rels),"functions":len(decls),"types":len(types),"direct_call_sites":direct,"unresolved_call_sites":unknown,"ambiguous_call_sites":ambiguous,"nodes":len(nodes),"edges":len(edges)}
 return map[string]any{"metadata":map[string]any{"scope":"PUBLIC_STAGE111_GO_AST_ONLY","sha":sha,"analysis":"go/parser AST; direct same-package calls and receiver methods; no runtime parity"},"counts":counts,"nodes":nodes,"edges":edges},nil
}
func main(){
 root:=flag.String("repo",".","repository root");sha:=flag.String("sha","UNPINNED","full commit SHA");out:=flag.String("out","docs/architecture/mvkview-recovery/stage111-go-callgraph.json","output JSON")
 flag.Parse()
 data,err:=analyze(*root,*sha);if err!=nil{fmt.Fprintln(os.Stderr,err);os.Exit(2)}
 dest:=*out;if !filepath.IsAbs(dest){dest=filepath.Join(*root,dest)}
 if err=os.MkdirAll(filepath.Dir(dest),0755);err!=nil{fmt.Fprintln(os.Stderr,err);os.Exit(2)}
 b,err:=json.MarshalIndent(data,"","  ");if err!=nil{fmt.Fprintln(os.Stderr,err);os.Exit(2)}
 if err=os.WriteFile(dest,append(b,'\n'),0644);err!=nil{fmt.Fprintln(os.Stderr,err);os.Exit(2)}
 fmt.Printf("Stage111 Go AST: %v\n",data["counts"])
}