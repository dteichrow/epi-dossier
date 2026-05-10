# Remotion Atlas Scaffold

This directory is intentionally lightweight in v1.

The live Pathogen Atlas runs as static HTML plus JavaScript. Remotion is reserved for optional motion assets so the atlas never depends on video to function.

Planned compositions:

1. `AtlasHeroLoop`
   - slow editorial motion plate for the main `atlas.html` hero
   - rotates through selected pathogens
2. `RouteExplainer`
   - short route fly-through for one pathogen at a time
   - good for share clips and blog embeds
3. `EvidenceGradeExplainer`
   - simple animation that explains consensus vs mixed vs contested atlas claims
4. `SpecimenReveal`
   - editorial reveal of atlas art assets once generated and approved

Rules:

- motion assets are optional enhancements
- authoritative geometry still comes from `config/pathogen_atlas.yml`
- no map logic should depend on rendered video output
- any generated assets should be tracked in `graphics/atlas/manifest.yml`
