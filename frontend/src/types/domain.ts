/**
 * Narrowed re-exports of the auto-generated OpenAPI schema
 * (src/api/generated/schema.d.ts, regenerated via `npm run generate:api`).
 *
 * App code imports these friendly names instead of reaching into
 * `components['schemas'][...]` everywhere — one indirection layer so the rest
 * of the app never depends on openapi-typescript's exact output shape.
 */

import type { components } from '../api/generated/schema'

type Schemas = components['schemas']

export type CompanyProfile = Schemas['CompanyProfile']
export type CompanyListResponse = Schemas['CompanyListResponse']
export type RankedSatellite = Schemas['RankedSatellite']
export type CorrelationResponse = Schemas['CorrelationResponse']
export type PricePoint = Schemas['PricePoint']
export type PriceHistoryResponse = Schemas['PriceHistoryResponse']
export type GraphNode = Schemas['GraphNode']
export type GraphEdge = Schemas['GraphEdge']
export type GraphResponse = Schemas['GraphResponse']
export type RelatednessResponse = Schemas['RelatednessResponse']
