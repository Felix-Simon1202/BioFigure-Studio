"""Expanded component IDs remain valid across the full project contract."""
import pytest
from pydantic import ValidationError
from backend.core.specs import IllustrationSpec, IllustrationNode


def test_full_component_library_roundtrip_and_legacy_ids():
    identifiers = IllustrationNode.model_json_schema()['properties']['component_id']['enum']
    assert len(identifiers) == 28
    assert {'cell_generic', 'nucleus_generic', 'receptor_membrane', 'ligand_generic'}.issubset(identifiers)
    nodes = [dict(id=f'node_{index}', component_id=component, x=40, y=40, width=100, height=80,
                  label='Original 科学标签', entity_type='context', scientific_status='illustrative')
             for index, component in enumerate(identifiers)]
    document = IllustrationSpec.model_validate(dict(spec_version='1.3', document_kind='mechanism',
        title='Synthetic component library', canvas=dict(width=960, height=640, background='#ffffff'),
        nodes=nodes, edges=[], groups=[], sections=[], flow_links=[], evidence_records=[],
        provenance=dict(registry_version='1.0', mechanism_schema_version='1.0', composition_schema_version='1.0',
                        component_ids=identifiers, note='Synthetic review')))
    assert IllustrationSpec.model_validate_json(document.model_dump_json()) == document
    assert all(node.scientific_status == 'illustrative' for node in document.nodes)
    with pytest.raises(ValidationError):
        IllustrationNode.model_validate({**nodes[0], 'component_id': 'unreviewed_remote_svg'})
