import time

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from frontend.st_utils import get_backend_api_client, initialize_st_page

initialize_st_page(
    title="Trading Hub",
    icon="💹",
    layout="wide",
    show_readme=False
)

# Initialize backend client
backend_api_client = get_backend_api_client()

# Initialize session state
if "selected_account" not in st.session_state:
    st.session_state.selected_account = None
if "selected_connector" not in st.session_state:
    st.session_state.selected_connector = None
if "selected_market" not in st.session_state:
    st.session_state.selected_market = {"connector": "binance_perpetual", "trading_pair": "BTC-USDT"}
if "candles_connector" not in st.session_state:
    st.session_state.candles_connector = None
if "auto_refresh_enabled" not in st.session_state:
    st.session_state.auto_refresh_enabled = False  # Start with manual refresh
if "chart_interval" not in st.session_state:
    st.session_state.chart_interval = "1m"
if "max_candles" not in st.session_state:
    st.session_state.max_candles = 100  # Reduced for better performance

# Set refresh interval for real-time updates
REFRESH_INTERVAL = 30  # seconds


def get_accounts_and_credentials():
    """Get available accounts and their credentials."""
    try:
        accounts_list = backend_api_client.accounts.list_accounts()
        credentials_list = {}
        for account in accounts_list:
            credentials = backend_api_client.accounts.list_credentials(account)
            credentials_list[account] = credentials
        return accounts_list, credentials_list
    except Exception as e:
        st.error(f"Failed to fetch accounts: {e}")
        return [], {}


def get_candles_connectors():
    """Get available candles feed connectors."""
    try:
        return backend_api_client.market_data.get_available_candles_feed()
    except Exception as e:
        st.warning(f"Could not fetch candles feed connectors: {e}")
        return []


def get_positions():
    """Get current positions."""
    try:
        response = backend_api_client.trading.get_positions(limit=100)
        # Handle both response formats
        if isinstance(response, list):
            return response
        elif isinstance(response, dict) and response.get("status") == "success":
            return response.get("data", [])
        return []
    except Exception as e:
        st.error(f"Failed to fetch positions: {e}")
        return []


def get_active_orders():
    """Get active orders."""
    try:
        response = backend_api_client.trading.get_active_orders(limit=100)
        # Handle both response formats
        if isinstance(response, list):
            return response
        elif isinstance(response, dict) and response.get("status") == "success":
            return response.get("data", [])
        return []
    except Exception as e:
        st.error(f"Failed to fetch active orders: {e}")
        return []


def get_order_history():
    """Get recent order history."""
    try:
        # Try to get orders instead of order_history since that method doesn't exist
        response = backend_api_client.trading.get_orders(limit=50)
        # Handle both response formats
        if isinstance(response, list):
            return response
        elif isinstance(response, dict) and response.get("status") == "success":
            return response.get("data", [])
        return []
    except Exception:
        # If get_orders doesn't exist either, just return empty list without warning
        return []


def get_market_data(connector, trading_pair, interval="1m", max_records=100, candles_connector=None):
    """Get market data with proper error handling."""
    start_time = time.time()
    try:
        # Get candles
        candles = []
        try:
            # Use candles_connector if provided, otherwise use main connector
            candles_conn = candles_connector if candles_connector else connector
            candles_response = backend_api_client.market_data.get_candles(
                connector=candles_conn,
                trading_pair=trading_pair,
                interval=interval,
                max_records=max_records
            )
            # Handle both response formats
            if isinstance(candles_response, list):
                # Direct list response
                candles = candles_response
            elif isinstance(candles_response, dict) and candles_response.get("status") == "success":
                # Response object with status and data
                candles = candles_response.get("data", [])
        except Exception as e:
            st.warning(f"Could not fetch candles: {e}")

        # Get current price
        prices = {}
        try:
            price_response = backend_api_client.market_data.get_prices(
                connector=connector,
                trading_pairs=[trading_pair]
            )
            # Handle both response formats
            if isinstance(price_response, dict):
                if "status" in price_response and price_response.get("status") == "success":
                    prices = price_response.get("data", {})
                elif "prices" in price_response:
                    # Response has a "prices" field containing the actual price data
                    prices = price_response.get("prices", {})
                else:
                    # Direct dict response with prices
                    prices = price_response
            elif isinstance(price_response, list):
                # If it's a list, try to convert to dict
                prices = {item.get("trading_pair", "unknown"): item.get("price", 0) for item in price_response if
                          isinstance(item, dict)}
        except Exception as e:
            st.warning(f"Could not fetch prices: {e}")

        # Calculate fetch time for performance monitoring
        fetch_time = (time.time() - start_time) * 1000
        st.session_state["last_fetch_time"] = fetch_time
        st.session_state["last_fetch_timestamp"] = time.time()

        return candles, prices
    except Exception as e:
        st.error(f"Failed to fetch market data: {e}")
        return [], {}


def place_order(order_data):
    """Place a trading order."""
    try:
        response = backend_api_client.trading.place_order(**order_data)
        if response.get("status") == "success":
            st.success(f"Order placed successfully! Order ID: {response.get('order_id')}")
            return True
        else:
            st.error(f"Failed to place order: {response.get('message', 'Unknown error')}")
            return False
    except Exception as e:
        st.error(f"Failed to place order: {e}")
        return False


def cancel_order(account_name, connector_name, order_id):
    """Cancel an order."""
    try:
        response = backend_api_client.trading.cancel_order(
            account_name=account_name,
            connector_name=connector_name,
            client_order_id=order_id
        )
        if response.get("status") == "success":
            st.success(f"Order {order_id} cancelled successfully!")
            return True
        else:
            st.error(f"Failed to cancel order: {response.get('message', 'Unknown error')}")
            return False
    except Exception as e:
        st.error(f"Failed to cancel order: {e}")
        return False


def get_default_layout(title=None, height=800, width=1100):
    layout = {
        "template": "plotly_dark",
        "plot_bgcolor": 'rgba(0, 0, 0, 0)',  # Transparent background
        "paper_bgcolor": 'rgba(0, 0, 0, 0.1)',  # Lighter shade for the paper
        "font": {"color": 'white', "size": 12},  # Consistent font color and size
        "height": height,
        "width": width,
        "margin": {"l": 20, "r": 20, "t": 50, "b": 20},
        "xaxis_rangeslider_visible": False,
        "hovermode": "x unified",
        "showlegend": False,
    }
    if title:
        layout["title"] = title
    return layout


def create_candlestick_chart(candles_data, connector_name="", trading_pair="", interval=""):
    """Create a candlestick chart with custom theme."""
    if not candles_data:
        fig = go.Figure()
        fig.add_annotation(
            text="No candle data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False
        )
        fig.update_layout(**get_default_layout(height=600))
        return fig

    try:
        # Convert candles data to DataFrame
        df = pd.DataFrame(candles_data)
        if df.empty:
            return go.Figure()

        # Convert timestamp to datetime for better display
        if 'timestamp' in df.columns:
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')

        # Create candlestick chart
        fig = go.Figure()

        # Add candlestick trace
        fig.add_trace(
            go.Candlestick(
                x=df['datetime'] if 'datetime' in df.columns else df.index,
                open=df['open'],
                high=df['high'],
                low=df['low'],
                close=df['close'],
                name="Candlesticks",
                increasing_line_color='#2ECC71',
                decreasing_line_color='#E74C3C'
            )
        )

        # Create title
        title = f"{connector_name}: {trading_pair} ({interval})" if connector_name else "Price Chart"

        # Update layout with custom theme
        fig.update_layout(**get_default_layout(title=title, height=600))

        return fig
    except Exception as e:
        # Fallback chart with error message
        fig = go.Figure()
        fig.add_annotation(
            text=f"Error creating chart: {str(e)}",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False
        )
        fig.update_layout(**get_default_layout(height=600))
        return fig


def render_positions_table(positions_data):
    """Render positions table."""
    if not positions_data:
        st.info("No open positions found.")
        return

    # Convert to DataFrame for better display
    df = pd.DataFrame(positions_data)
    if df.empty:
        st.info("No open positions found.")
        return

    st.subheader("🎯 Open Positions")

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "unrealized_pnl": st.column_config.NumberColumn(
                "Unrealized PnL",
                format="$%.2f"
            ),
            "entry_price": st.column_config.NumberColumn(
                "Entry Price",
                format="$%.4f"
            ),
            "mark_price": st.column_config.NumberColumn(
                "Mark Price",
                format="$%.4f"
            ),
            "amount": st.column_config.NumberColumn(
                "Amount",
                format="%.6f"
            )
        }
    )


def render_orders_table(orders_data):
    """Render active orders table."""
    if not orders_data:
        st.info("No active orders found.")
        return

    # Convert to DataFrame
    df = pd.DataFrame(orders_data)
    if df.empty:
        st.info("No active orders found.")
        return

    st.subheader("📋 Active Orders")

    # Add cancel button functionality
    edited_df = st.data_editor(
        df,
        column_config={
            "cancel": st.column_config.CheckboxColumn(
                "Cancel",
                help="Select orders to cancel",
                default=False,
            ),
            "price": st.column_config.NumberColumn(
                "Price",
                format="$%.4f"
            ),
            "amount": st.column_config.NumberColumn(
                "Amount",
                format="%.6f"
            )
        },
        disabled=[col for col in df.columns if col != "cancel"],
        hide_index=True,
        use_container_width=True,
        key="orders_editor"
    )

    # Handle order cancellation
    if "cancel" in edited_df.columns:
        selected_orders = edited_df[edited_df["cancel"]]
        if not selected_orders.empty and st.button(f"❌ Cancel Selected ({len(selected_orders)}) Orders",
                                                   type="secondary"):
            with st.spinner("Cancelling orders..."):
                for _, order in selected_orders.iterrows():
                    cancel_order(
                        order.get("account_name", ""),
                        order.get("connector_name", ""),
                        order.get("client_order_id", "")
                    )
            st.rerun()


# Page Header
st.header("💹 Trading Hub")
st.caption("Execute trades, monitor positions, and analyze markets")

# Get accounts and credentials
accounts_list, credentials_dict = get_accounts_and_credentials()
candles_connectors = get_candles_connectors()

# Account and Trading Selection Section
st.subheader("🏦 Account & Market Selection")

# First row: Account and credentials selection
col1, col2, col3 = st.columns([1, 1, 1])

with col1:
    if accounts_list:
        # Default to first account if not set
        if st.session_state.selected_account is None:
            st.session_state.selected_account = accounts_list[0]

        selected_account = st.selectbox(
            "📱 Account",
            accounts_list,
            index=accounts_list.index(
                st.session_state.selected_account) if st.session_state.selected_account in accounts_list else 0,
            key="account_selector"
        )
        st.session_state.selected_account = selected_account
    else:
        st.error("No accounts found")
        st.stop()

with col2:
    if selected_account and credentials_dict.get(selected_account):
        credentials = credentials_dict[selected_account]
        # Filter for BTC-USDT trading pair
        btc_credentials = [cred for cred in credentials if "BTC-USDT" in cred.get("trading_pairs", [])]

        if btc_credentials:
            # Default to first BTC-USDT credential
            default_cred = btc_credentials[0]
        else:
            # Fallback to first credential
            default_cred = credentials[0] if credentials else None

        if default_cred:
            connector = st.selectbox(
                "📡 Exchange",
                [cred["connector_name"] for cred in credentials],
                index=[cred["connector_name"] for cred in credentials].index(default_cred["connector_name"]),
                key="connector_selector"
            )
            st.session_state.selected_connector = connector
        else:
            st.error("No credentials found for this account")
            connector = None
    else:
        st.error("No credentials available")
        connector = None

with col3:
    trading_pair = st.text_input(
        "💱 Trading Pair",
        value="BTC-USDT",
        key="trading_pair_input"
    )

# Update selected market
if connector and trading_pair:
    st.session_state.selected_market = {"connector": connector, "trading_pair": trading_pair}

# Second row: Chart settings and candles connector
col1, col2, col3, col4 = st.columns([1, 1, 1, 1])

with col1:
    interval = st.selectbox(
        "⏱️ Chart Interval",
        ["1m", "3m", "5m", "15m", "1h", "4h", "1d"],
        index=0,
        key="interval_selector"
    )
    st.session_state.chart_interval = interval

with col2:
    if candles_connectors:
        # Add option to use same connector as trading
        candles_options = ["Same as trading"] + candles_connectors
        selected_candles = st.selectbox(
            "📊 Candles Source",
            candles_options,
            index=0,
            key="candles_connector_selector",
            help="Some exchanges don't provide candles. Select an alternative source."
        )
        st.session_state.candles_connector = None if selected_candles == "Same as trading" else selected_candles
    else:
        st.session_state.candles_connector = None

with col3:
    max_candles = st.number_input(
        "📈 Max Candles",
        min_value=50,
        max_value=500,
        value=100,
        step=50,
        key="max_candles_input"
    )
    st.session_state.max_candles = max_candles

with col4:
    if st.button("🔄 Refresh Data", use_container_width=True, type="primary"):
        st.rerun()

st.divider()


# Simplified display function without auto-refresh
def show_trading_data():
    """Fragment to display trading data with simplified layout."""
    connector = st.session_state.selected_market.get("connector")
    trading_pair = st.session_state.selected_market.get("trading_pair")
    interval = st.session_state.chart_interval
    max_candles = st.session_state.max_candles
    candles_connector = st.session_state.candles_connector

    if not connector or not trading_pair:
        st.warning("Please select an account and trading pair")
        return

    # Get market data
    candles, prices = get_market_data(
        connector, trading_pair, interval, max_candles, candles_connector
    )

    # Show current price and status
    price_col1, price_col2, price_col3 = st.columns([2, 2, 2])

    with price_col1:
        if prices and trading_pair in prices:
            current_price = prices[trading_pair]
            st.metric(
                f"💰 {trading_pair} Price",
                f"${float(current_price):,.2f}"
            )
        else:
            st.metric(f"💰 {trading_pair} Price", "Loading...")

    with price_col2:
        st.metric("⏱️ Interval", f"{interval}")
        if candles:
            st.caption(f"📈 {len(candles)} candles")

    with price_col3:
        if "last_fetch_time" in st.session_state:
            fetch_time = st.session_state["last_fetch_time"]
            st.metric("⚡ Fetch Time", f"{fetch_time:.0f}ms")

    # Chart section
    st.divider()
    candles_source = candles_connector if candles_connector else connector
    fig = create_candlestick_chart(candles, candles_source, trading_pair, interval)
    st.plotly_chart(fig, use_container_width=True)

    # Data tables section
    st.divider()

    # Get positions, orders, and history
    positions = get_positions()
    orders = get_active_orders()
    order_history = get_order_history()

    # Display in tabs - Balances first
    tab1, tab2, tab3, tab4 = st.tabs(["💰 Balances", "📊 Positions", "📋 Active Orders", "📜 Order History"])

    with tab1:
        render_balances_table()
    with tab2:
        render_positions_table(positions)
    with tab3:
        render_orders_table(orders)
    with tab4:
        render_order_history_table(order_history)


def render_order_history_table(order_history):
    """Render order history table."""
    if not order_history:
        st.info("No order history found.")
        return

    # Convert to DataFrame
    df = pd.DataFrame(order_history)
    if df.empty:
        st.info("No order history found.")
        return

    st.subheader("📜 Order History")
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "price": st.column_config.NumberColumn(
                "Price",
                format="$%.4f"
            ),
            "amount": st.column_config.NumberColumn(
                "Amount",
                format="%.6f"
            ),
            "timestamp": st.column_config.DatetimeColumn(
                "Time",
                format="DD/MM/YYYY HH:mm:ss"
            )
        }
    )


def get_balances():
    """Get account balances."""
    try:
        if not st.session_state.selected_account:
            return []

        # Get portfolio state for the selected account
        portfolio_state = backend_api_client.portfolio.get_state(
            account_names=[st.session_state.selected_account]
        )

        # Extract balances
        balances = []
        if st.session_state.selected_account in portfolio_state:
            for exchange, tokens in portfolio_state[st.session_state.selected_account].items():
                for token_info in tokens:
                    balances.append({
                        "exchange": exchange,
                        "token": token_info["token"],
                        "total": token_info["units"],
                        "available": token_info["available_units"],
                        "price": token_info["price"],
                        "value": token_info["value"]
                    })
        return balances
    except Exception as e:
        st.error(f"Failed to fetch balances: {e}")
        return []


def render_balances_table():
    """Render balances table."""
    balances = get_balances()

    if not balances:
        st.info("No balances found.")
        return

    # Convert to DataFrame
    df = pd.DataFrame(balances)
    if df.empty:
        st.info("No balances found.")
        return

    st.subheader(f"💰 Account Balances - {st.session_state.selected_account}")

    # Calculate total value
    total_value = df['value'].sum()
    st.metric("Total Portfolio Value", f"${total_value:,.2f}")

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "total": st.column_config.NumberColumn(
                "Total Balance",
                format="%.6f"
            ),
            "available": st.column_config.NumberColumn(
                "Available",
                format="%.6f"
            ),
            "price": st.column_config.NumberColumn(
                "Price",
                format="$%.4f"
            ),
            "value": st.column_config.NumberColumn(
                "Value (USD)",
                format="$%.2f"
            )
        }
    )


# Trade Execution Section
st.subheader("💸 Execute Trade")

if st.session_state.selected_account and st.session_state.selected_connector:
    exec_col1, exec_col2, exec_col3, exec_col4 = st.columns([1, 1, 1, 1])

    with exec_col1:
        order_type = st.selectbox(
            "Order Type",
            ["market", "limit"],
            key="order_type"
        )

    with exec_col2:
        side = st.selectbox(
            "Side",
            ["buy", "sell"],
            key="order_side"
        )

    with exec_col3:
        amount = st.number_input(
            "Amount",
            min_value=0.0,
            value=0.001,
            format="%.6f",
            key="order_amount"
        )

    with exec_col4:
        if order_type == "limit":
            price = st.number_input(
                "Price",
                min_value=0.0,
                value=0.0,
                format="%.4f",
                key="order_price"
            )
        else:
            price = None

    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        if st.button("🚀 Place Order", type="primary", use_container_width=True):
            if amount > 0:
                order_data = {
                    "account_name": st.session_state.selected_account,
                    "connector_name": st.session_state.selected_connector,
                    "trading_pair": st.session_state.selected_market["trading_pair"],
                    "order_type": order_type,
                    "trade_type": side,
                    "amount": amount
                }
                if order_type == "limit" and price:
                    order_data["price"] = price

                place_order(order_data)
            else:
                st.error("Please enter a valid amount")

    with col3:
        st.info(
            f"🎯 Trading on {st.session_state.selected_connector} with {st.session_state.selected_market['trading_pair']}")
else:
    st.warning("Please select an account and exchange to execute trades")

st.divider()

# Call the fragment
show_trading_data()
