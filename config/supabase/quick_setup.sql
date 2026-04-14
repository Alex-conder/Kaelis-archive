-- Kaelis Quick Setup SQL
-- Execute this in Supabase SQL Editor: https://app.supabase.io/project/wlktdlkekmkjhhdlvwjv/editor

-- 1. Create profiles table (extends auth.users)
create table if not exists profiles (
  id uuid references auth.users on delete cascade primary key,
  email text not null,
  username text not null unique,
  avatar_url text,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- Enable RLS
alter table profiles enable row level security;

-- RLS Policies
create policy "Users can view own profile" on profiles for select using (auth.uid() = id);
create policy "Users can update own profile" on profiles for update using (auth.uid() = id);

-- 2. Create workflows table
create table if not exists workflows (
  id uuid default gen_random_uuid() primary key,
  user_id uuid references profiles(id) on delete cascade not null,
  name text not null,
  description text,
  nodes jsonb default '[]'::jsonb,
  edges jsonb default '[]'::jsonb,
  is_public boolean default false,
  version integer default 1,
  created_at timestamptz default now(),
  updated_at timestamptz default now(),
  synced_at timestamptz
);

alter table workflows enable row level security;

create policy "Users can view own workflows" on workflows for select using (auth.uid() = user_id);
create policy "Users can create own workflows" on workflows for insert with check (auth.uid() = user_id);
create policy "Users can update own workflows" on workflows for update using (auth.uid() = user_id);
create policy "Users can delete own workflows" on workflows for delete using (auth.uid() = user_id);
create policy "Public workflows viewable" on workflows for select using (is_public = true);

-- 3. Create sync_logs table
create table if not exists sync_logs (
  id uuid default gen_random_uuid() primary key,
  user_id uuid references profiles(id) on delete cascade not null,
  workflow_id uuid references workflows(id) on delete cascade,
  operation text not null,
  status text not null,
  details jsonb,
  created_at timestamptz default now()
);

alter table sync_logs enable row level security;

create policy "Users can view own sync logs" on sync_logs for select using (auth.uid() = user_id);
create policy "Users can create own sync logs" on sync_logs for insert with check (auth.uid() = user_id);

-- 4. Create indexes
create index if not exists idx_workflows_user_id on workflows(user_id);
create index if not exists idx_workflows_updated_at on workflows(updated_at);
create index if not exists idx_sync_logs_user_id on sync_logs(user_id);

-- 5. Create updated_at trigger function
create or replace function update_updated_at_column()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

-- 6. Apply triggers
drop trigger if exists update_profiles_updated_at on profiles;
create trigger update_profiles_updated_at before update on profiles for each row execute function update_updated_at_column();

drop trigger if exists update_workflows_updated_at on workflows;
create trigger update_workflows_updated_at before update on workflows for each row execute function update_updated_at_column();

-- Success message
select 'Kaelis database schema created successfully!' as status;
