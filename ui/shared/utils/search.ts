export interface SearchParams {
  location?: string | null
  checkin?: string | null
  nights?: number | null
  checkout?: string | null
  keywords?: string[] | null
  match_all_keywords?: boolean
  amenities?: string[] | null
  min_price?: number | null
  max_price?: number | null
  min_rating?: number | null
  guests?: number | null
  room_type?: string | null
  superhost?: boolean
  instant_book?: boolean
  self_checkin?: boolean
  min_bedrooms?: number | null
  min_beds?: number | null
  min_bathrooms?: number | null
  max_listings?: number | null
  max_pages?: number | null
  use_vision?: boolean
  top_k?: number | null
}

export interface SearchOption {
  label: string
  value: string
}

export interface ListingResult {
  title: string
  url: string
  city?: string
  price?: number | null
  total_price?: number | null
  rating?: number | null
  description?: string
  image_url?: string | null
  image_urls?: string[]
  amenities?: string[]
  house_rules?: string[]
  matched_keywords?: string[]
  match_score?: number | null
  vision_score?: number | null
}

export const ROOM_TYPES: SearchOption[] = [
  { label: 'Apartment', value: 'apartment' },
  { label: 'Entire home', value: 'entire_home' },
  { label: 'Private room', value: 'private_room' },
  { label: 'Shared room', value: 'shared_room' },
  { label: 'Hotel room', value: 'hotel_room' }
]

export const AMENITIES: SearchOption[] = [
  { label: 'Wi-Fi', value: 'wifi' },
  { label: 'Kitchen', value: 'kitchen' },
  { label: 'Washer', value: 'washer' },
  { label: 'Dryer', value: 'dryer' },
  { label: 'Air conditioning', value: 'air_conditioning' },
  { label: 'Heating', value: 'heating' },
  { label: 'Pool', value: 'pool' },
  { label: 'Hot tub', value: 'hot_tub' },
  { label: 'Gym', value: 'gym' },
  { label: 'Free parking', value: 'free_parking' },
  { label: 'EV charger', value: 'ev_charger' },
  { label: 'Crib', value: 'crib' },
  { label: 'BBQ grill', value: 'bbq_grill' },
  { label: 'Breakfast', value: 'breakfast' },
  { label: 'Fireplace', value: 'fireplace' },
  { label: 'Workspace', value: 'workspace' },
  { label: 'TV', value: 'tv' },
  { label: 'Pets allowed', value: 'pets_allowed' },
  { label: 'Smoking allowed', value: 'smoking_allowed' },
  { label: 'Wheelchair accessible', value: 'wheelchair_accessible' },
  { label: 'Elevator', value: 'elevator' },
  { label: 'Beach access', value: 'beach_access' },
  { label: 'Waterfront', value: 'waterfront' },
  { label: 'Self check-in', value: 'self_checkin' }
]

export function toSearchPayload(search: SearchParams | null | undefined): Record<string, unknown> | undefined {
  if (!search) return undefined

  const out: Record<string, unknown> = {}
  if (search.location?.trim()) out.location = search.location.trim()
  if (search.checkin) out.checkin = search.checkin
  if (search.checkout) out.checkout = search.checkout
  if (search.nights != null) out.nights = search.nights
  if (search.min_price != null) out.min_price = search.min_price
  if (search.max_price != null) out.max_price = search.max_price
  if (search.min_rating != null) out.min_rating = search.min_rating
  if (search.guests != null) out.guests = search.guests
  if (search.room_type) out.room_type = search.room_type
  if (search.amenities?.length) out.amenities = search.amenities
  if (search.keywords?.length) out.keywords = search.keywords
  if (search.match_all_keywords) out.match_all_keywords = true
  if (search.superhost) out.superhost = true
  if (search.instant_book) out.instant_book = true
  if (search.self_checkin) out.self_checkin = true
  if (search.min_bedrooms != null) out.min_bedrooms = search.min_bedrooms
  if (search.min_beds != null) out.min_beds = search.min_beds
  if (search.min_bathrooms != null) out.min_bathrooms = search.min_bathrooms
  if (search.max_listings != null) out.max_listings = search.max_listings
  if (search.max_pages != null) out.max_pages = search.max_pages
  if (search.use_vision) out.use_vision = true
  if (search.top_k != null) out.top_k = search.top_k

  return Object.keys(out).length ? out : undefined
}

export function applySearchUpdate(current: SearchParams, incoming: Record<string, unknown>): SearchParams {
  return { ...current, ...incoming } as SearchParams
}

export type ChatStreamEvent =
  | { type: 'status', message: string }
  | { type: 'text', delta: string }
  | { type: 'search', data: Record<string, unknown> }
  | { type: 'listings', data: ListingResult[] }
  | { type: 'error', message: string }
  | { type: 'done' }

export function parseChatStreamEvent(line: string): ChatStreamEvent | null {
  try {
    const event = JSON.parse(line) as Partial<ChatStreamEvent>
    if (event.type === 'done') return { type: 'done' }
    if (event.type === 'status' && typeof event.message === 'string') {
      return { type: 'status', message: event.message }
    }
    if (event.type === 'text' && typeof event.delta === 'string') {
      return { type: 'text', delta: event.delta }
    }
    if (event.type === 'search' && event.data && typeof event.data === 'object') {
      return { type: 'search', data: event.data as Record<string, unknown> }
    }
    if (event.type === 'listings' && Array.isArray(event.data)) {
      return { type: 'listings', data: event.data as ListingResult[] }
    }
    if (event.type === 'error' && typeof event.message === 'string') {
      return { type: 'error', message: event.message }
    }
  } catch {
    // A partial line is buffered by the caller; malformed complete lines are ignored.
  }
  return null
}
