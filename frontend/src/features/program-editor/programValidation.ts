import { z } from 'zod'
import type { TFunction } from 'i18next'
import type { Program, Room, RoomType, Typology } from '../../types/project'

export const ROOM_TYPE_VALUES: RoomType[] = [
  'LIVING',
  'KITCHEN',
  'BEDROOM',
  'BATHROOM',
  'CORRIDOR',
  'STORAGE',
  'PARKING',
]

export type FieldErrors = Record<string, string>

function createRoomSchema(t: TFunction) {
  return z.object({
    type: z
      .string()
      .refine((value) => ROOM_TYPE_VALUES.includes(value as RoomType), t('program_editor.validation.room_type_required')),
    min_area: z.number().positive(t('program_editor.validation.positive_number')),
    min_short_side: z.number().positive(t('program_editor.validation.positive_number')),
  })
}

export function createTypologySchema(
  t: TFunction,
  existingIds: string[],
  currentId?: string,
) {
  return z
    .object({
      id: z.string().trim().min(1, t('program_editor.validation.required')),
      name: z.string().trim().min(1, t('program_editor.validation.required')),
      min_useful_area: z.number().positive(t('program_editor.validation.positive_number')),
      max_useful_area: z.number().positive(t('program_editor.validation.positive_number')),
      num_bedrooms: z.number().int().min(0, t('program_editor.validation.non_negative_integer')),
      num_bathrooms: z.number().int().min(1, t('program_editor.validation.bathrooms_minimum')),
      rooms: z.array(createRoomSchema(t)).min(1, t('program_editor.validation.rooms_required')),
    })
    .superRefine((value, context) => {
      if (value.min_useful_area >= value.max_useful_area) {
        context.addIssue({
          code: 'custom',
          path: ['max_useful_area'],
          message: t('program_editor.validation.area_range'),
        })
      }

      if (!value.rooms.some((room) => room.type === 'LIVING')) {
        context.addIssue({
          code: 'custom',
          path: ['rooms'],
          message: t('program_editor.validation.living_required'),
        })
      }

      if (existingIds.includes(value.id) && value.id !== currentId) {
        context.addIssue({
          code: 'custom',
          path: ['id'],
          message: t('program_editor.validation.typology_id_unique'),
        })
      }
    })
}

export function createProgramSchema(t: TFunction) {
  const typologySchema = z.object({
    id: z.string().trim().min(1, t('program_editor.validation.required')),
    name: z.string().trim().min(1, t('program_editor.validation.required')),
    min_useful_area: z.number().positive(t('program_editor.validation.positive_number')),
    max_useful_area: z.number().positive(t('program_editor.validation.positive_number')),
    num_bedrooms: z.number().int().min(0, t('program_editor.validation.non_negative_integer')),
    num_bathrooms: z.number().int().min(1, t('program_editor.validation.bathrooms_minimum')),
    rooms: z.array(createRoomSchema(t)).min(1, t('program_editor.validation.rooms_required')),
  })

  return z
    .object({
      project_id: z.string().trim().min(1),
      num_floors: z.number().int().min(1, t('program_editor.validation.floors_minimum')),
      floor_height_m: z.number().positive(t('program_editor.validation.positive_number')),
      typologies: z.array(typologySchema).min(1, t('program_editor.validation.typologies_required')),
      mix: z
        .array(
          z.object({
            typology_id: z.string().trim().min(1),
            count: z.number().int().min(1, t('program_editor.validation.mix_minimum')),
          }),
        )
        .min(1, t('program_editor.validation.mix_required')),
    })
    .superRefine((value, context) => {
      const knownIds = new Set<string>()
      for (const [index, typology] of value.typologies.entries()) {
        if (knownIds.has(typology.id)) {
          context.addIssue({
            code: 'custom',
            path: ['typologies', index, 'id'],
            message: t('program_editor.validation.typology_id_unique'),
          })
        }
        knownIds.add(typology.id)

        if (typology.min_useful_area >= typology.max_useful_area) {
          context.addIssue({
            code: 'custom',
            path: ['typologies', index, 'max_useful_area'],
            message: t('program_editor.validation.area_range'),
          })
        }

        if (!typology.rooms.some((room) => room.type === 'LIVING')) {
          context.addIssue({
            code: 'custom',
            path: ['typologies', index, 'rooms'],
            message: t('program_editor.validation.living_required'),
          })
        }
      }

      for (const [index, entry] of value.mix.entries()) {
        if (!knownIds.has(entry.typology_id)) {
          context.addIssue({
            code: 'custom',
            path: ['mix', index, 'typology_id'],
            message: t('program_editor.validation.mix_unknown_typology'),
          })
        }
      }

      for (const typologyId of knownIds) {
        if (!value.mix.some((entry) => entry.typology_id === typologyId)) {
          context.addIssue({
            code: 'custom',
            path: ['mix'],
            message: t('program_editor.validation.mix_missing_entry'),
          })
        }
      }
    })
}

export function mapZodIssues(error: z.ZodError): FieldErrors {
  return error.issues.reduce<FieldErrors>((collection, issue) => {
    const key = issue.path.join('.') || 'root'
    if (!collection[key]) {
      collection[key] = issue.message
    }
    return collection
  }, {})
}

export function createEmptyRoom(): Room {
  return {
    type: 'LIVING',
    min_area: 20,
    min_short_side: 3.2,
  }
}

export function createEmptyTypology(): Typology {
  return {
    id: '',
    name: '',
    min_useful_area: 60,
    max_useful_area: 85,
    num_bedrooms: 2,
    num_bathrooms: 1,
    rooms: [createEmptyRoom()],
  }
}

export function synchronizeMix(program: Program): Program {
  const counts = new Map(program.mix.map((entry) => [entry.typology_id, entry.count]))
  return {
    ...program,
    mix: program.typologies.map((typology) => ({
      typology_id: typology.id,
      count: counts.get(typology.id) ?? 1,
    })),
  }
}