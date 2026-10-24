"""Public entry points and source-bound results for bounded compiled tools."""
import ast
import hashlib
import keyword


def read(artifact):
    if not isinstance(artifact,dict) or artifact.get('schema')!=1:
        raise ValueError('Unsupported tool artifact')
    name=artifact.get('entrypoint');source=artifact.get('source')
    if not isinstance(name,str) or not name.isidentifier() or keyword.iskeyword(name) or name.startswith('_'):
        raise ValueError('Invalid public tool entry point')
    if not isinstance(source,str) or len(source)>20000 or hashlib.sha256(source.encode()).hexdigest()!=artifact.get('sha256'):
        raise ValueError('Tool source checksum mismatch')
    try:tree=ast.parse(source)
    except (SyntaxError,RecursionError) as error:raise ValueError('Invalid tool source') from error
    if sum(1 for _ in ast.walk(tree))>1500 or sum(isinstance(n,ast.FunctionDef) and n.name==name for n in tree.body)!=1:
        raise ValueError('Missing or ambiguous tool entry point')
    return artifact


def attach(answer,name,source,domain,checks,has_result=False,value=None):
    artifact=dict(schema=1,entrypoint=name,source=source,sha256=hashlib.sha256(source.encode()).hexdigest(),
                  domain=domain,checks=checks,validation='bounded compiler/plan agreement; not proof of intent')
    read(artifact)
    answer=dict(answer,python_tool=artifact)
    if has_result:
        answer['tool_result']=dict(status='value',value=value,source_sha256=artifact['sha256'])
    return answer
