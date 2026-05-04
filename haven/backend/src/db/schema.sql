-- Haven database schema (run in Supabase SQL editor)

create extension if not exists "uuid-ossp";

-- Users
create table users (
  id uuid primary key default uuid_generate_v4(),
  email text unique not null,
  password_hash text not null,
  kyc_status text not null default 'pending',  -- pending | approved | rejected
  kyc_provider_id text,                         -- Persona inquiry ID
  solana_pubkey text,
  first_name text,
  created_at timestamptz not null default now()
);

-- Wallets (one per user)
create table wallets (
  id uuid primary key default uuid_generate_v4(),
  user_id uuid not null references users(id) on delete cascade,
  balance_usd numeric(18,6) not null default 0,
  balance_sol numeric(18,9) not null default 0,
  pending_withdrawal_usd numeric(18,6) not null default 0,
  total_earned_usd numeric(18,6) not null default 0,
  updated_at timestamptz not null default now()
);

-- Transactions
create type transaction_type as enum ('deposit', 'withdrawal', 'yield');
create type transaction_status as enum ('pending', 'processing', 'completed', 'failed');

create table transactions (
  id uuid primary key default uuid_generate_v4(),
  user_id uuid not null references users(id) on delete cascade,
  type transaction_type not null,
  amount_usd numeric(18,6) not null,
  amount_sol numeric(18,9),
  status transaction_status not null default 'pending',
  stripe_payment_id text,
  tx_signature text,    -- Solana transaction signature
  created_at timestamptz not null default now()
);

-- Yield logs (one row per user per day)
create table yield_logs (
  id uuid primary key default uuid_generate_v4(),
  user_id uuid not null references users(id) on delete cascade,
  date date not null,
  yield_usd numeric(18,6) not null,
  sol_price_at_time numeric(18,4),
  apy_at_time numeric(6,4),
  created_at timestamptz not null default now(),
  unique (user_id, date)
);

-- Indexes
create index on transactions(user_id, created_at desc);
create index on yield_logs(user_id, date desc);
create index on wallets(user_id);

-- Row Level Security (RLS) — enable via Supabase dashboard
-- Service role key (used by backend) bypasses RLS automatically.
