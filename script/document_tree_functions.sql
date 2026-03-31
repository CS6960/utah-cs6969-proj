-- Vector match function with depth filter.
create or replace function match_document_tree_nodes (
  query_embedding vector(4096),
  match_threshold float,
  match_count int,
  match_depth int
)
returns table (
  id uuid,
  parent_id uuid,
  title text,
  file_title text,
  text text,
  depth int,
  metadata jsonb,
  similarity float
)
language plpgsql
as $$
begin
  return query
  select
    d.id,
    d.parent_id,
    d.title,
    d.file_title,
    d.text,
    d.depth,
    d.metadata,
    1 - (d.embedding <=> query_embedding) as similarity
  from document_tree_nodes as d
  where d.depth <= match_depth
    and 1 - (d.embedding <=> query_embedding) > match_threshold
  order by d.embedding <=> query_embedding
  limit match_count;
end;
$$;


-- Traversal function from any node.
-- mode:
--   'up'   -> node -> parent -> ... -> root
--   'down' -> node -> children -> descendants
--   'both' -> union of up and down traversals
create or replace function traverse_document_tree_nodes (
  start_node_id uuid,
  mode text default 'up',
  max_hops int default 64
)
returns table (
  id uuid,
  parent_id uuid,
  title text,
  file_title text,
  text text,
  depth int,
  metadata jsonb,
  hop int,
  direction text
)
language plpgsql
as $$
begin
  if mode = 'up' then
    return query
    with recursive up_tree as (
      select
        d.id,
        d.parent_id,
        d.title,
        d.file_title,
        d.text,
        d.depth,
        d.metadata,
        0::int as hop
      from document_tree_nodes d
      where d.id = start_node_id

      union all

      select
        p.id,
        p.parent_id,
        p.title,
        p.file_title,
        p.text,
        p.depth,
        p.metadata,
        u.hop + 1
      from up_tree u
      join document_tree_nodes p on p.id = u.parent_id
      where u.hop < max_hops
    )
    select
      u.id,
      u.parent_id,
      u.title,
      u.file_title,
      u.text,
      u.depth,
      u.metadata,
      u.hop,
      'up'::text as direction
    from up_tree u
    order by u.hop asc;

  elsif mode = 'down' then
    return query
    with recursive down_tree as (
      select
        d.id,
        d.parent_id,
        d.title,
        d.file_title,
        d.text,
        d.depth,
        d.metadata,
        0::int as hop
      from document_tree_nodes d
      where d.id = start_node_id

      union all

      select
        c.id,
        c.parent_id,
        c.title,
        c.file_title,
        c.text,
        c.depth,
        c.metadata,
        dt.hop + 1
      from down_tree dt
      join document_tree_nodes c on c.parent_id = dt.id
      where dt.hop < max_hops
    )
    select
      d.id,
      d.parent_id,
      d.title,
      d.file_title,
      d.text,
      d.depth,
      d.metadata,
      d.hop,
      'down'::text as direction
    from down_tree d
    order by d.hop asc, d.depth asc;

  elsif mode = 'both' then
    return query
    with recursive up_tree as (
      select
        d.id,
        d.parent_id,
        d.title,
        d.file_title,
        d.text,
        d.depth,
        d.metadata,
        0::int as hop
      from document_tree_nodes d
      where d.id = start_node_id

      union all

      select
        p.id,
        p.parent_id,
        p.title,
        p.file_title,
        p.text,
        p.depth,
        p.metadata,
        u.hop + 1
      from up_tree u
      join document_tree_nodes p on p.id = u.parent_id
      where u.hop < max_hops
    ),
    down_tree as (
      select
        d.id,
        d.parent_id,
        d.title,
        d.file_title,
        d.text,
        d.depth,
        d.metadata,
        0::int as hop
      from document_tree_nodes d
      where d.id = start_node_id

      union all

      select
        c.id,
        c.parent_id,
        c.title,
        c.file_title,
        c.text,
        c.depth,
        c.metadata,
        dt.hop + 1
      from down_tree dt
      join document_tree_nodes c on c.parent_id = dt.id
      where dt.hop < max_hops
    )
    select distinct
      x.id,
      x.parent_id,
      x.title,
      x.file_title,
      x.text,
      x.depth,
      x.metadata,
      x.hop,
      x.direction
    from (
      select
        u.id,
        u.parent_id,
        u.title,
        u.file_title,
        u.text,
        u.depth,
        u.metadata,
        u.hop,
        'up'::text as direction
      from up_tree u
      union all
      select
        d.id,
        d.parent_id,
        d.title,
        d.file_title,
        d.text,
        d.depth,
        d.metadata,
        d.hop,
        'down'::text as direction
      from down_tree d
    ) x
    order by x.direction, x.hop asc, x.depth asc;

  else
    raise exception 'Invalid mode: %. Use up, down, or both.', mode;
  end if;
end;
$$;
