-- Supabase Database Schema
-- P1 Task: Supabase Authentication + Workflow Cloud Sync
-- Run this in Supabase SQL Editor

-- Enable RLS
alter default privileges in schema public grant all on tables to postgres, anon, authenticated, service_role;

-- Profiles table (extends auth.users)
create table if not exists profiles (
  id uuid references auth.users on delete cascade primary key,
  email text not null,
  username text not null unique,
  avatar_url text,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- Enable RLS on profiles
alter table profiles enable row level security;

-- RLS Policies for profiles
create policy "Users can view own profile"
  on profiles for select
  using (auth.uid() = id);

create policy "Users can update own profile"
  on profiles for update
  using (auth.uid() = id);

-- Workflows table
create table if not exists workflows (
  id uuid default gen_random_uuid() primary key,
  user_id uuid references profiles(id) on delete cascade not null,
  name text not null,
  description text,
  nodes jsonb not null default '[]'::jsonb,
  edges jsonb not null default '[]'::jsonb,
  is_public boolean default false,
  version integer default 1,
  created_at timestamptz default now(),
  updated_at timestamptz default now(),
  synced_at timestamptz
);

-- Enable RLS on workflows
alter table workflows enable row level security;

-- RLS Policies for workflows
create policy "Users can view own workflows"
  on workflows for select
  using (auth.uid() = user_id);

create policy "Users can create own workflows"
  on workflows for insert
  with check (auth.uid() = user_id);

create policy "Users can update own workflows"
  on workflows for update
  using (auth.uid() = user_id);

create policy "Users can delete own workflows"
  on workflows for delete
  using (auth.uid() = user_id);

-- Public workflows can be viewed by anyone
create policy "Anyone can view public workflows"
  on workflows for select
  using (is_public = true);

-- Indexes for performance
create index if not exists idx_workflows_user_id on workflows(user_id);
create index if not exists idx_workflows_updated_at on workflows(updated_at);
create index if not exists idx_workflows_is_public on workflows(is_public) where is_public = true;

-- Function to update updated_at timestamp
create or replace function update_updated_at_column()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

-- Triggers for updated_at
create trigger update_profiles_updated_at
  before update on profiles
  for each row
  execute function update_updated_at_column();

create trigger update_workflows_updated_at
  before update on workflows
  for each row
  execute function update_updated_at_column();

-- Sync log table for tracking sync operations
create table if not exists sync_logs (
  id uuid default gen_random_uuid() primary key,
  user_id uuid references profiles(id) on delete cascade not null,
  workflow_id uuid references workflows(id) on delete cascade,
  operation text not null, -- 'push', 'pull', 'conflict'
  status text not null, -- 'success', 'error', 'conflict'
  details jsonb,
  created_at timestamptz default now()
);

-- Enable RLS on sync_logs
alter table sync_logs enable row level security;

create policy "Users can view own sync logs"
  on sync_logs for select
  using (auth.uid() = user_id);

create policy "Users can create own sync logs"
  on sync_logs for insert
  with check (auth.uid() = user_id);

-- Index for sync logs
create index if not exists idx_sync_logs_user_id on sync_logs(user_id);
create index if not exists idx_sync_logs_created_at on sync_logs(created_at);

-- Storage bucket for workflow assets (images, exports)
insert into storage.buckets (id, name, public)
values ('workflows', 'workflows', false)
on conflict (id) do nothing;

-- Storage policy for workflow assets
create policy "Users can upload own workflow assets"
  on storage.objects for insert
  with check (
    bucket_id = 'workflows' and
    auth.uid()::text = (storage.foldername(name))[1]
  );

create policy "Users can view own workflow assets"
  on storage.objects for select
  using (
    bucket_id = 'workflows' and
    auth.uid()::text = (storage.foldername(name))[1]
  );

create policy "Users can delete own workflow assets"
  on storage.objects for delete
  using (
    bucket_id = 'workflows' and
    auth.uid()::text = (storage.foldername(name))[1]
  );
