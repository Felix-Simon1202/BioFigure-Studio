# DeepTutor attribution and modifications

Source: HKUDS/DeepTutor, contributors to that project.
Repository: https://github.com/HKUDS/DeepTutor
Reviewed commit: 60fb3bdfddb30b7740c7ce3bd9b28d908f2af6db
License: Apache License 2.0, reproduced in LICENSE in this directory.

The active-persona block framing in backend/core/biodot.py is adapted from
deeptutor/services/persona/service.py, PersonaService.load_for_context.
The fixed voice/playbook is informed by the peer and research-assistant
PERSONA.md presets in deeptutor/services/persona/presets. Short voice and
evidence instructions are retained, with a BioFigure-specific identity.

Modifications: fixed Biodot identity; scientific-drawing workflow instead of
tutoring; no account/workspace file operations or configurable persona loader;
task schemas, tool permissions and consent remain authoritative. The derived
biodot.py module is distributed under Apache-2.0. Other original project code
remains MIT; no DeepTutor service runtime or dependency is included.

Reviewed upstream file SHA-256:

- LICENSE: cd2f54e1e5066644023203dcbd956776a9f4ef6eb8b6225afe1ffa2d380fede4
- service.py: 603e01d651cf4125305ee85491f4e65f8f4e71285d7afe6c206259061ae8bdbf
- peer/PERSONA.md: 90360f7b7a09c90ef1c0f72c22e584685f7e7bb75fb5dfd3834f4d5ead874b27
- research-assistant/PERSONA.md: 1ce9db116e388a71d378cccc6659448a59bd517061493675d5c63bbfdbac4c29
