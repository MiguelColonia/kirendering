import type { Program, ProjectPayload, Solar } from '../../types/project'

export function createDefaultSolar(): Solar {
  return {
    id: 'grundstueck-entwurf',
    contour: {
      points: [
        { x: 0, y: 0 },
        { x: 24, y: 0 },
        { x: 28, y: 14 },
        { x: 22, y: 30 },
        { x: 0, y: 28 },
      ],
    },
    north_angle_deg: 0,
    max_buildable_height_m: 21,
  }
}

export function createDefaultProgram(): Program {
  return {
    project_id: 'projekt-entwurf',
    num_floors: 4,
    floor_height_m: 3,
    typologies: [
      {
        id: 'T2',
        name: 'Wohneinheit T2',
        min_useful_area: 72,
        max_useful_area: 94,
        num_bedrooms: 2,
        num_bathrooms: 1,
        rooms: [
          { type: 'LIVING', min_area: 22, min_short_side: 3.8 },
          { type: 'KITCHEN', min_area: 8, min_short_side: 2.2 },
          { type: 'BEDROOM', min_area: 12, min_short_side: 2.8 },
          { type: 'BATHROOM', min_area: 4.5, min_short_side: 1.8 },
          { type: 'CORRIDOR', min_area: 5, min_short_side: 1.2 },
        ],
      },
    ],
    mix: [{ typology_id: 'T2', count: 12 }],
  }
}

export function createProjectSeedPayload(name: string, description: string): ProjectPayload {
  return {
    name,
    description: description || null,
    solar: createDefaultSolar(),
    program: createDefaultProgram(),
  }
}