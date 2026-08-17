CREATE TABLE "accounts" (
	"id" text PRIMARY KEY NOT NULL,
	"user_id" text NOT NULL,
	"account_id" text NOT NULL,
	"provider_id" text NOT NULL,
	"access_token" text,
	"refresh_token" text,
	"access_token_expires_at" timestamp with time zone,
	"refresh_token_expires_at" timestamp with time zone,
	"scope" text,
	"id_token" text,
	"password" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "api_keys" (
	"id" serial PRIMARY KEY NOT NULL,
	"user_id" text,
	"name" text NOT NULL,
	"key_hash" text NOT NULL,
	"key_prefix" text NOT NULL,
	"rate_limit_per_minute" integer DEFAULT 60 NOT NULL,
	"rate_limit_per_day" integer DEFAULT 10000 NOT NULL,
	"total_requests" bigint DEFAULT 0 NOT NULL,
	"total_rows_returned" bigint DEFAULT 0 NOT NULL,
	"last_used_at" timestamp with time zone,
	"revoked_at" timestamp with time zone,
	"expires_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "api_usage" (
	"api_key_id" integer NOT NULL,
	"window" text NOT NULL,
	"window_start" timestamp with time zone NOT NULL,
	"request_count" integer DEFAULT 0 NOT NULL,
	"rows_returned" bigint DEFAULT 0 NOT NULL,
	CONSTRAINT "api_usage_api_key_id_window_window_start_pk" PRIMARY KEY("api_key_id","window","window_start")
);
--> statement-breakpoint
CREATE TABLE "companies" (
	"id" serial PRIMARY KEY NOT NULL,
	"apex" text NOT NULL,
	"name" text,
	"description" text,
	"category" text,
	"country" text,
	"website" text,
	"confidence" double precision,
	"field_sources" jsonb,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "ct_log_state" (
	"log_url" text PRIMARY KEY NOT NULL,
	"description" text,
	"next_index" bigint DEFAULT 0 NOT NULL,
	"tree_size" bigint DEFAULT 0 NOT NULL,
	"last_event_at" timestamp with time zone,
	"last_error_at" timestamp with time zone,
	"last_error" text,
	"consecutive_failures" integer DEFAULT 0 NOT NULL,
	"entries_processed" bigint DEFAULT 0 NOT NULL,
	"enabled" boolean DEFAULT true NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "deliveries" (
	"id" serial PRIMARY KEY NOT NULL,
	"kind" text NOT NULL,
	"webhook_id" integer,
	"saved_search_id" integer,
	"target" text NOT NULL,
	"payload_summary" jsonb,
	"domain_count" integer DEFAULT 0 NOT NULL,
	"status" text DEFAULT 'pending' NOT NULL,
	"status_code" integer,
	"attempt" integer DEFAULT 0 NOT NULL,
	"error" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"delivered_at" timestamp with time zone
);
--> statement-breakpoint
CREATE TABLE "domain_dns" (
	"id" serial PRIMARY KEY NOT NULL,
	"apex" text NOT NULL,
	"a_records" jsonb DEFAULT '[]'::jsonb NOT NULL,
	"aaaa_records" jsonb DEFAULT '[]'::jsonb NOT NULL,
	"mx_records" jsonb DEFAULT '[]'::jsonb NOT NULL,
	"ns_records" jsonb DEFAULT '[]'::jsonb NOT NULL,
	"txt_records" jsonb DEFAULT '[]'::jsonb NOT NULL,
	"has_spf" boolean DEFAULT false NOT NULL,
	"has_dmarc" boolean DEFAULT false NOT NULL,
	"mx_provider" text,
	"mx_provider_kind" text,
	"changed_from_previous" boolean DEFAULT false NOT NULL,
	"ns_changed" boolean DEFAULT false NOT NULL,
	"is_current" boolean DEFAULT true NOT NULL,
	"resolved_at" timestamp with time zone DEFAULT now() NOT NULL,
	"last_attempted_at" timestamp with time zone DEFAULT now() NOT NULL,
	"failure_count" integer DEFAULT 0 NOT NULL,
	"last_error" text
);
--> statement-breakpoint
CREATE TABLE "domain_http" (
	"id" serial PRIMARY KEY NOT NULL,
	"apex" text NOT NULL,
	"requested_url" text,
	"status_code" integer,
	"final_url" text,
	"redirect_count" integer DEFAULT 0 NOT NULL,
	"redirected_off_domain" boolean DEFAULT false NOT NULL,
	"title" text,
	"meta_description" text,
	"body_snippet" text,
	"lang" text,
	"tech" jsonb DEFAULT '[]'::jsonb NOT NULL,
	"server" text,
	"is_parked" boolean DEFAULT false NOT NULL,
	"parking_vendor" text,
	"parking_reason" text,
	"robots_allowed" boolean DEFAULT true NOT NULL,
	"content_length" integer,
	"response_time_ms" integer,
	"is_current" boolean DEFAULT true NOT NULL,
	"probed_at" timestamp with time zone DEFAULT now() NOT NULL,
	"last_attempted_at" timestamp with time zone DEFAULT now() NOT NULL,
	"failure_count" integer DEFAULT 0 NOT NULL,
	"last_error" text
);
--> statement-breakpoint
CREATE TABLE "domain_rdap" (
	"id" serial PRIMARY KEY NOT NULL,
	"apex" text NOT NULL,
	"registrar" text,
	"registrar_iana_id" text,
	"created_date" timestamp with time zone,
	"expires_date" timestamp with time zone,
	"last_changed_date" timestamp with time zone,
	"statuses" jsonb DEFAULT '[]'::jsonb NOT NULL,
	"nameservers" jsonb DEFAULT '[]'::jsonb NOT NULL,
	"registrant_country" text,
	"registrant_state" text,
	"had_redactions" boolean DEFAULT false NOT NULL,
	"rdap_server" text,
	"is_current" boolean DEFAULT true NOT NULL,
	"fetched_at" timestamp with time zone DEFAULT now() NOT NULL,
	"last_attempted_at" timestamp with time zone DEFAULT now() NOT NULL,
	"failure_count" integer DEFAULT 0 NOT NULL,
	"last_error" text
);
--> statement-breakpoint
CREATE TABLE "domain_scores" (
	"id" serial PRIMARY KEY NOT NULL,
	"apex" text NOT NULL,
	"score" integer NOT NULL,
	"tier" text NOT NULL,
	"reason" text NOT NULL,
	"rules_verdict" text NOT NULL,
	"rules_kill_reason" text,
	"rules_signals" jsonb,
	"classifier_ran" boolean DEFAULT false NOT NULL,
	"is_real_business" boolean,
	"category" text,
	"stage_guess" text,
	"confidence" double precision,
	"classifier_reason" text,
	"model_version" text,
	"scoring_version" text NOT NULL,
	"is_current" boolean DEFAULT true NOT NULL,
	"scored_at" timestamp with time zone DEFAULT now() NOT NULL,
	"last_attempted_at" timestamp with time zone DEFAULT now() NOT NULL,
	"failure_count" integer DEFAULT 0 NOT NULL,
	"last_error" text
);
--> statement-breakpoint
CREATE TABLE "domains" (
	"id" serial PRIMARY KEY NOT NULL,
	"apex" text NOT NULL,
	"tld" text NOT NULL,
	"first_seen_at" timestamp with time zone DEFAULT now() NOT NULL,
	"last_seen_at" timestamp with time zone DEFAULT now() NOT NULL,
	"source" text NOT NULL,
	"registration_date" timestamp with time zone,
	"registration_date_source" text,
	"status" text DEFAULT 'discovered' NOT NULL,
	"is_suppressed" boolean DEFAULT false NOT NULL,
	"ct_hit_count" integer DEFAULT 0 NOT NULL,
	"requeue_after" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "enrichment_costs" (
	"id" serial PRIMARY KEY NOT NULL,
	"apex" text NOT NULL,
	"stage" text NOT NULL,
	"micro_usd" integer NOT NULL,
	"detail" jsonb,
	"incurred_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "feed_runs" (
	"id" serial PRIMARY KEY NOT NULL,
	"feed" text NOT NULL,
	"feed_date" text NOT NULL,
	"status" text NOT NULL,
	"domains_in_file" integer,
	"domains_inserted" integer,
	"bytes_downloaded" bigint,
	"warning" text,
	"error" text,
	"started_at" timestamp with time zone DEFAULT now() NOT NULL,
	"finished_at" timestamp with time zone
);
--> statement-breakpoint
CREATE TABLE "opt_outs" (
	"id" serial PRIMARY KEY NOT NULL,
	"apex" text NOT NULL,
	"verification_token" text NOT NULL,
	"verified_at" timestamp with time zone,
	"verification_attempts" integer DEFAULT 0 NOT NULL,
	"last_attempted_at" timestamp with time zone,
	"last_error" text,
	"requester_email" text,
	"requested_at" timestamp with time zone DEFAULT now() NOT NULL,
	"note" text
);
--> statement-breakpoint
CREATE TABLE "saved_searches" (
	"id" serial PRIMARY KEY NOT NULL,
	"user_id" text NOT NULL,
	"name" text NOT NULL,
	"filters" jsonb NOT NULL,
	"digest_enabled" boolean DEFAULT false NOT NULL,
	"digest_hour_utc" smallint DEFAULT 13 NOT NULL,
	"last_digest_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "sessions" (
	"id" text PRIMARY KEY NOT NULL,
	"user_id" text NOT NULL,
	"token" text NOT NULL,
	"expires_at" timestamp with time zone NOT NULL,
	"ip_address" text,
	"user_agent" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "users" (
	"id" text PRIMARY KEY NOT NULL,
	"name" text DEFAULT '' NOT NULL,
	"email" text NOT NULL,
	"email_verified" boolean DEFAULT false NOT NULL,
	"image" text,
	"role" text DEFAULT 'user' NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "verifications" (
	"id" text PRIMARY KEY NOT NULL,
	"identifier" text NOT NULL,
	"value" text NOT NULL,
	"expires_at" timestamp with time zone NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "webhooks" (
	"id" serial PRIMARY KEY NOT NULL,
	"user_id" text NOT NULL,
	"url" text NOT NULL,
	"secret" text NOT NULL,
	"saved_search_id" integer,
	"filters" jsonb,
	"active" boolean DEFAULT true NOT NULL,
	"last_delivered_score_id" integer DEFAULT 0 NOT NULL,
	"consecutive_failures" integer DEFAULT 0 NOT NULL,
	"disabled_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
ALTER TABLE "accounts" ADD CONSTRAINT "accounts_user_id_users_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "api_keys" ADD CONSTRAINT "api_keys_user_id_users_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "api_usage" ADD CONSTRAINT "api_usage_api_key_id_api_keys_id_fk" FOREIGN KEY ("api_key_id") REFERENCES "public"."api_keys"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "deliveries" ADD CONSTRAINT "deliveries_webhook_id_webhooks_id_fk" FOREIGN KEY ("webhook_id") REFERENCES "public"."webhooks"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "deliveries" ADD CONSTRAINT "deliveries_saved_search_id_saved_searches_id_fk" FOREIGN KEY ("saved_search_id") REFERENCES "public"."saved_searches"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "saved_searches" ADD CONSTRAINT "saved_searches_user_id_users_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "sessions" ADD CONSTRAINT "sessions_user_id_users_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "webhooks" ADD CONSTRAINT "webhooks_user_id_users_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "webhooks" ADD CONSTRAINT "webhooks_saved_search_id_saved_searches_id_fk" FOREIGN KEY ("saved_search_id") REFERENCES "public"."saved_searches"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
CREATE INDEX "accounts_user_idx" ON "accounts" USING btree ("user_id");--> statement-breakpoint
CREATE UNIQUE INDEX "api_keys_hash_key" ON "api_keys" USING btree ("key_hash");--> statement-breakpoint
CREATE INDEX "api_keys_user_idx" ON "api_keys" USING btree ("user_id");--> statement-breakpoint
CREATE INDEX "api_usage_window_idx" ON "api_usage" USING btree ("window_start");--> statement-breakpoint
CREATE UNIQUE INDEX "companies_apex_key" ON "companies" USING btree ("apex");--> statement-breakpoint
CREATE INDEX "companies_category_idx" ON "companies" USING btree ("category");--> statement-breakpoint
CREATE INDEX "companies_country_idx" ON "companies" USING btree ("country");--> statement-breakpoint
CREATE INDEX "deliveries_webhook_idx" ON "deliveries" USING btree ("webhook_id","created_at");--> statement-breakpoint
CREATE INDEX "deliveries_status_idx" ON "deliveries" USING btree ("status");--> statement-breakpoint
CREATE INDEX "domain_dns_apex_idx" ON "domain_dns" USING btree ("apex","resolved_at");--> statement-breakpoint
CREATE UNIQUE INDEX "domain_dns_current_key" ON "domain_dns" USING btree ("apex") WHERE "domain_dns"."is_current";--> statement-breakpoint
CREATE INDEX "domain_dns_mx_provider_idx" ON "domain_dns" USING btree ("mx_provider");--> statement-breakpoint
CREATE INDEX "domain_http_apex_idx" ON "domain_http" USING btree ("apex","probed_at");--> statement-breakpoint
CREATE UNIQUE INDEX "domain_http_current_key" ON "domain_http" USING btree ("apex") WHERE "domain_http"."is_current";--> statement-breakpoint
CREATE INDEX "domain_http_parked_idx" ON "domain_http" USING btree ("is_parked");--> statement-breakpoint
CREATE INDEX "domain_rdap_apex_idx" ON "domain_rdap" USING btree ("apex","fetched_at");--> statement-breakpoint
CREATE UNIQUE INDEX "domain_rdap_current_key" ON "domain_rdap" USING btree ("apex") WHERE "domain_rdap"."is_current";--> statement-breakpoint
CREATE INDEX "domain_rdap_registrar_idx" ON "domain_rdap" USING btree ("registrar");--> statement-breakpoint
CREATE INDEX "domain_rdap_country_idx" ON "domain_rdap" USING btree ("registrant_country");--> statement-breakpoint
CREATE INDEX "domain_scores_apex_idx" ON "domain_scores" USING btree ("apex","scored_at");--> statement-breakpoint
CREATE UNIQUE INDEX "domain_scores_current_key" ON "domain_scores" USING btree ("apex") WHERE "domain_scores"."is_current";--> statement-breakpoint
CREATE INDEX "domain_scores_score_idx" ON "domain_scores" USING btree ("score","scored_at");--> statement-breakpoint
CREATE INDEX "domain_scores_tier_idx" ON "domain_scores" USING btree ("tier");--> statement-breakpoint
CREATE INDEX "domain_scores_category_idx" ON "domain_scores" USING btree ("category");--> statement-breakpoint
CREATE UNIQUE INDEX "domains_apex_key" ON "domains" USING btree ("apex");--> statement-breakpoint
CREATE INDEX "domains_status_idx" ON "domains" USING btree ("status");--> statement-breakpoint
CREATE INDEX "domains_first_seen_idx" ON "domains" USING btree ("first_seen_at");--> statement-breakpoint
CREATE INDEX "domains_tld_idx" ON "domains" USING btree ("tld");--> statement-breakpoint
CREATE INDEX "domains_status_requeue_idx" ON "domains" USING btree ("status","requeue_after");--> statement-breakpoint
CREATE INDEX "enrichment_costs_apex_idx" ON "enrichment_costs" USING btree ("apex");--> statement-breakpoint
CREATE INDEX "enrichment_costs_incurred_idx" ON "enrichment_costs" USING btree ("incurred_at");--> statement-breakpoint
CREATE UNIQUE INDEX "feed_runs_feed_date_key" ON "feed_runs" USING btree ("feed","feed_date");--> statement-breakpoint
CREATE INDEX "feed_runs_status_idx" ON "feed_runs" USING btree ("status","started_at");--> statement-breakpoint
CREATE UNIQUE INDEX "opt_outs_apex_key" ON "opt_outs" USING btree ("apex");--> statement-breakpoint
CREATE INDEX "opt_outs_verified_idx" ON "opt_outs" USING btree ("verified_at");--> statement-breakpoint
CREATE INDEX "saved_searches_user_idx" ON "saved_searches" USING btree ("user_id");--> statement-breakpoint
CREATE INDEX "saved_searches_digest_idx" ON "saved_searches" USING btree ("digest_enabled");--> statement-breakpoint
CREATE UNIQUE INDEX "sessions_token_key" ON "sessions" USING btree ("token");--> statement-breakpoint
CREATE INDEX "sessions_user_idx" ON "sessions" USING btree ("user_id");--> statement-breakpoint
CREATE UNIQUE INDEX "users_email_key" ON "users" USING btree ("email");--> statement-breakpoint
CREATE INDEX "verifications_identifier_idx" ON "verifications" USING btree ("identifier");--> statement-breakpoint
CREATE INDEX "webhooks_user_idx" ON "webhooks" USING btree ("user_id");--> statement-breakpoint
CREATE INDEX "webhooks_active_idx" ON "webhooks" USING btree ("active");