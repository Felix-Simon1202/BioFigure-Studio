"""Selected-object local editing: proposals are pure, bounded and reviewable."""
import json
import re
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from backend.core.specs import IllustrationSpec
from backend.core.figure_consistency import fingerprint


class EditIntent(BaseModel):
    model_config=ConfigDict(extra='forbid', strict=True)
    operation: Literal['color','label','move','align','size']
    color: str | None = Field(default=None, pattern=r'^#[0-9a-fA-F]{6}$')
    text: str | None = Field(default=None,max_length=200)
    x: float | None = Field(default=None,ge=0,le=4000)
    y: float | None = Field(default=None,ge=0,le=4000)
    width: float | None = Field(default=None,ge=24,le=800)
    height: float | None = Field(default=None,ge=24,le=800)
    align: Literal['left','right','top','bottom'] | None = None


class EditRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    document: IllustrationSpec
    selected_ids: list[str] = Field(min_length=1,max_length=200)
    prompt: str = Field(min_length=1,max_length=600)
    provider: Literal['rules','local'] = 'rules'


def parse_edit(prompt: str) -> EditIntent:
    value=prompt.strip()
    color=re.fullmatch(r'(?:color|colour|颜色|改色|配色)\s*[:：]?\s*(#[0-9a-fA-F]{6})',value,re.I)
    if color: return EditIntent(operation='color',color=color[1])
    label=re.fullmatch(r'(?:label|rename|标签|改标签)\s*[:：]\s*(.+)',value,re.I)
    if label: return EditIntent(operation='label',text=label[1])
    match=re.fullmatch(r'(move|移动|size|尺寸)\s*[:：]?\s*(\d+(?:\.\d+)?)\s*[,，x× ]\s*(\d+(?:\.\d+)?)',value,re.I)
    if match:
        a,b=float(match[2]),float(match[3])
        return EditIntent(operation='move',x=a,y=b) if match[1].lower() in {'move','移动'} else EditIntent(operation='size',width=a,height=b)
    aligns={'left':'left','right':'right','top':'top','bottom':'bottom','左':'left','右':'right','上':'top','下':'bottom'}
    match=re.fullmatch(r'(?:align\s+(left|right|top|bottom)|(左|右|上|下)对齐)',value,re.I)
    if match: return EditIntent(operation='align',align=aligns[(match[1] or match[2]).lower()])
    raise ValueError('Use color #RRGGBB; label: text; move x,y; size width,height; or align left/right/top/bottom.')


def preview_edit(request: EditRequest, model=None) -> dict:
    before=request.document.model_dump(mode='json')
    ids=set(request.selected_ids)
    targets=[node for node in request.document.nodes if node.id in ids]
    if len(ids)!=len(request.selected_ids) or len(targets)!=len(ids):
        raise ValueError('Select existing nodes exactly once.')
    if any(node.scientific_status=='verified' for node in targets):
        raise ValueError('Verified objects are protected. Review their status manually before editing.')
    if request.provider=='local':
        if len(targets)>8: raise ValueError('Select at most eight nodes for a local model proposal.')
        if model is None:
            from backend.core.workbench import _model_object, ensure_reviewed_local_model
            ensure_reviewed_local_model()
            model=_model_object
        context=[{'id':node.id,'label':node.label[:80],'x':node.x,'y':node.y,'width':node.width,'height':node.height} for node in targets]
        task=('Return a JSON EditIntent for the explicitly selected illustration nodes. No tools/code. Preserve scientific meaning. '
              'Emit only the requested operation fields: color => operation,color (#RRGGBB); label => operation,text; '
              'move => operation,x,y; size => operation,width,height; align => operation,align. '
              'Omit all unrelated fields or set them null, never zero/empty placeholders. Never output node IDs. '
              'Example for blue: {"operation":"color","color":"#1971c2"}. Selected local context: '+json.dumps(context,ensure_ascii=False))
        intent=EditIntent.model_validate(model(request.prompt,task,EditIntent.model_json_schema()))
    else: intent=parse_edit(request.prompt)
    needed={'color':{'color'},'label':{'text'},'move':{'x','y'},'size':{'width','height'},'align':{'align'}}[intent.operation]
    supplied={key for key,value in intent.model_dump().items() if key!='operation' and value is not None}
    if supplied!=needed: raise ValueError('The edit contains missing or unrelated fields.')
    if intent.operation in {'label','size'} and len(targets)!=1: raise ValueError('Select one node for label or size changes.')
    if intent.operation=='align' and len(targets)<2: raise ValueError('Select at least two nodes to align.')
    if intent.operation in {'align','size'} and any(node.rotation!=0 for node in targets):
        raise ValueError('Use unrotated nodes for alignment or resizing.')
    after=json.loads(json.dumps(before));changes=[]
    left=min(n.x for n in targets);top=min(n.y for n in targets)
    right=max(n.x+n.width for n in targets);bottom=max(n.y+n.height for n in targets)
    for node in after['nodes']:
        if node['id'] not in ids: continue
        if intent.operation=='color': patch={'fill':intent.color}
        elif intent.operation=='label': patch={'label':intent.text}
        elif intent.operation=='size': patch={'width':intent.width,'height':intent.height}
        elif intent.operation=='move': patch={'x':node['x']+intent.x-left,'y':node['y']+intent.y-top}
        else:
            patch={'x':left} if intent.align=='left' else {'x':right-node['width']} if intent.align=='right' else {'y':top} if intent.align=='top' else {'y':bottom-node['height']}
        for key,value in patch.items():
            if node[key]!=value:
                changes.append({'target':node['id'],'field':key,'before':node[key],'after':value});node[key]=value
    result=IllustrationSpec.model_validate(after)
    return {'document':result.model_dump(mode='json'),'changes':changes,'before_fingerprint':fingerprint(before),
            'provider':request.provider,'intent':intent.model_dump(exclude_none=True),'source_data_changed':False}
