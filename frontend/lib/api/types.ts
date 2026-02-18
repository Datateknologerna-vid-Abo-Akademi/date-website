export interface ThemePalette {
  background: string;
  surface: string;
  text: string;
  text_muted: string;
  primary: string;
  secondary: string;
  accent: string;
  border: string;
}

export interface AssociationTheme {
  brand: string;
  font_heading: string;
  font_body: string;
  palette: ThemePalette;
}

export interface StaticUrl {
  title: string;
  url: string;
  logged_in_only: boolean;
  dropdown_element: number;
}

export interface SiteNavCategory {
  category_name: string;
  nav_element: number;
  use_category_url: boolean;
  url: string;
  urls: StaticUrl[];
}

export interface SiteMeta {
  project_name: string;
  language_code: string;
  content_variables: Record<string, unknown>;
  association_theme: AssociationTheme;
  captcha_site_key: string;
  navigation: SiteNavCategory[];
  feature_flags: string[];
}

export interface ApiSuccess<T> {
  data: T;
}

export interface ApiError {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
}

export interface SessionData {
  is_authenticated: boolean;
  username?: string;
  full_name?: string;
  email?: string;
}

export interface NewsItem {
  title: string;
  slug: string;
  content: string;
  published_time: string | null;
  author_name: string;
  category_name: string | null;
  category_slug: string | null;
}

export interface EventItem {
  title: string;
  slug: string;
  content: string;
  event_date_start: string;
  event_date_end: string;
  members_only: boolean;
  sign_up: boolean;
  sign_up_avec: boolean;
  sign_up_max_participants: number;
  registration_open_members: boolean;
  registration_open_others: boolean;
  registration_past_due: boolean;
  event_full: boolean;
  redirect_link: string;
  image_url: string | null;
  sign_up_fields: Array<{
    name: string;
    type: string;
    required: boolean;
    public_info: boolean;
    choices: string[];
    hide_for_avec: boolean;
  }>;
  passcode_required?: boolean;
  passcode_verified?: boolean;
  registration_count?: number;
}

export interface HomePayload {
  events: EventItem[];
  news: NewsItem[];
  news_events: Array<{
    kind: "event" | "news";
    title: string;
    slug: string;
    date: string;
  }>;
  ads: Array<{ ad_url: string; company_url: string }>;
  instagram_posts: Array<{ url: string; shortcode: string }>;
  aa_post: NewsItem | null;
  calendar_events: Record<
    string,
    {
      link: string;
      modifier: string;
      eventFullDate: string;
      eventTitle: string;
    }
  >;
}

export interface StaticPage {
  title: string;
  slug: string;
  content: string;
  members_only: boolean;
  created_time: string;
  modified_time: string | null;
}

export interface MemberProfile {
  username: string;
  email: string | null;
  first_name: string;
  last_name: string;
  phone: string;
  address: string;
  zip_code: string;
  city: string;
  country: string;
  year_of_admission: number | null;
  membership_type: string;
  active_subscription: string | null;
}

export interface FunctionaryRole {
  id: number;
  title: string;
  board: boolean;
}

export interface FunctionaryItem {
  id: number;
  year: number;
  member_name: string;
  functionary_role: FunctionaryRole;
}

export interface PublicFunctionaryPayload {
  board_functionaries_by_role: Record<string, FunctionaryItem[]>;
  functionaries_by_role: Record<string, FunctionaryItem[]>;
  distinct_years: number[];
  roles: FunctionaryRole[];
}

export interface PollChoice {
  id: number;
  choice_text: string;
  votes: number;
  vote_percentage: number;
}

export interface PollQuestion {
  id: number;
  question_text: string;
  pub_date: string;
  published: boolean;
  show_results: boolean;
  end_vote: boolean;
  multiple_choice: boolean;
  required_multiple_choices: number | null;
  voting_options: number;
  choices: PollChoice[];
  total_votes: number;
}
