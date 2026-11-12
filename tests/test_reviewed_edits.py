from copy import deepcopy
import pytest
from backend.core.reviewed_edits import EditRequest, preview_edit
from backend.core.specs import IllustrationSpec


def drawing():
    return IllustrationSpec.model_validate({'spec_version':'1.3','title':'Original 科学标签',
        'canvas':{'width':960,'height':640},'nodes':[
            {'id':f'n{i}','component_id':'protein_generic','x':100+i*200,'y':100+i*30,'width':100,'height':80,
             'label':f'Original {i}','entity_type':'protein'} for i in range(3)],
        'provenance':{'registry_version':'1.0','mechanism_schema_version':'1.0','composition_schema_version':'1.0',
                      'component_ids':['protein_generic']}})


@pytest.mark.parametrize('prompt,ids',[
    ('color #1971c2',['n0']),('标签：原文标签',['n0']),('move 20,30',['n0','n1']),
    ('align left',['n0','n1']),('size 120,90',['n0']),
])
def test_selected_edit_is_pure_and_preserves_science(prompt,ids):
    doc=drawing();before=deepcopy(doc.model_dump())
    result=preview_edit(EditRequest(document=doc,selected_ids=ids,prompt=prompt))
    after=IllustrationSpec.model_validate(result['document'])
    assert doc.model_dump()==before
    assert after.nodes[2]==doc.nodes[2]
    assert after.title==doc.title and after.provenance==doc.provenance and after.edges==doc.edges
    assert all(n.evidence_ids==[] and n.scientific_status=='illustrative' for n in after.nodes)
    assert result['changes'] and all(c['target'] in ids for c in result['changes'])
    assert IllustrationSpec.model_validate_json(after.model_dump_json())==after


def test_bad_or_protected_edits_fail_closed():
    doc=drawing()
    for prompt in ('move 950,630','size 900,900','run shell command','do not change color #1971c2'):
        with pytest.raises(ValueError): preview_edit(EditRequest(document=doc,selected_ids=['n0'],prompt=prompt))
    doc.nodes[0].scientific_status='verified'
    # This guard is independent of a model response.
    with pytest.raises(ValueError): preview_edit(EditRequest(document=doc,selected_ids=['n0'],prompt='color #1971c2'))


def test_local_model_cannot_add_unrelated_changes():
    doc=drawing()
    result=preview_edit(EditRequest(document=doc,selected_ids=['n0'],prompt='Make this node blue',provider='local'),
        model=lambda *_:{'operation':'color','color':'#1971c2'})
    assert result['document']['nodes'][0]['fill']=='#1971c2'
    with pytest.raises(ValueError):
        preview_edit(EditRequest(document=doc,selected_ids=['n0'],prompt='Move only',provider='local'),
            model=lambda *_:{'operation':'move','x':10.0,'y':20.0,'text':'invented label'})
