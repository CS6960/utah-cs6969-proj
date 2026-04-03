create table if not exists public.stocks (
    symbol text primary key,
    name text not null,
    exchange text not null default 'NASDAQ',
    currency text not null default 'USD',
    created_at timestamptz not null default timezone('utc', now()),
    constraint stocks_symbol_format check (symbol = upper(symbol)),
    constraint stocks_symbol_length check (char_length(symbol) between 1 and 10)
);

create table if not exists public.stock_prices (
    stock_symbol text not null references public.stocks(symbol) on delete cascade,
    trading_date date not null,
    close numeric(12, 2) not null,
    created_at timestamptz not null default timezone('utc', now()),
    primary key (stock_symbol, trading_date),
    constraint stock_prices_close_nonnegative check (close >= 0)
);

create index if not exists idx_stock_prices_stock_id_date
    on public.stock_prices (stock_symbol, trading_date desc);

create table if not exists public.portfolio_positions (
    stock_symbol text primary key references public.stocks(symbol) on delete cascade,
    shares numeric(18, 4) not null check (shares >= 0),
    avg_cost numeric(12, 2) not null check (avg_cost >= 0),
    updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.portfolio_cash (
    currency text primary key,
    cash_balance numeric(14, 2) not null check (cash_balance >= 0),
    updated_at timestamptz not null default timezone('utc', now()),
    constraint portfolio_cash_currency_format check (currency = upper(currency)),
    constraint portfolio_cash_currency_length check (char_length(currency) = 3)
);
