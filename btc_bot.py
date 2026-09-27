import logging
import requests
import pandas as pd
import ta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# Telegram Bot Token (Added)
TOKEN = "8413300540:AAEkieSDGtmNUVuT41ljhl6K9hG7wRP6Stg"

# Logging Configuration
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# -------------------------------------------------------------
# 1. Binance Live Data & Timeframe Rules
# -------------------------------------------------------------
TF_RULES = {
    '5m':  {'name': '⚡ M5 (Scalp)',      'sl': 50,   'tp': 100},
    '15m': {'name': '⏱️ M15 (Intraday)',   'sl': 100,  'tp': 200},
    '1h':  {'name': '📊 H1 (Day Trade)',   'sl': 250,  'tp': 500},
    '4h':  {'name': '📈 H4 (Swing)',       'sl': 500,  'tp': 1000},
    '1d':  {'name': '🏔️ D1 (Positional)',  'sl': 1000, 'tp': 2500}
}

def get_live_btc_data(timeframe='1h', limit=100):
    """Binance REST API se Real-time Candlestick Data fetch karta hai"""
    url = f"https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval={timeframe}&limit={limit}"
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        df = pd.DataFrame(data, columns=['time', 'open', 'high', 'low', 'close', 'volume', '_', '_', '_', '_', '_', '_'])
        df['close'] = df['close'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        return df
    except Exception as e:
        logging.error(f"Error fetching data from Binance: {e}")
        return None

def get_fear_and_greed():
    """Crypto Fear & Greed Index Fetcher"""
    try:
        res = requests.get("https://api.alternative.me/fng/", timeout=5).json()
        value = res['data'][0]['value']
        status = res['data'][0]['value_classification']
        return value, status
    except:
        return "N/A", "Unknown"

# -------------------------------------------------------------
# 2. Advanced Signal & Dynamic TP/SL Engine
# -------------------------------------------------------------
def analyze_market(timeframe):
    df = get_live_btc_data(timeframe)
    if df is None or df.empty:
        return None

    current_price = df['close'].iloc[-1]
    rule = TF_RULES[timeframe]

    # Technical Indicators Calculations
    rsi = ta.momentum.RSIIndicator(df['close'], window=14).rsi().iloc[-1]
    ema_20 = ta.trend.EMAIndicator(df['close'], window=20).ema_indicator().iloc[-1]
    ema_50 = ta.trend.EMAIndicator(df['close'], window=50).ema_indicator().iloc[-1]

    # Dynamic Signal Logic
    if current_price > ema_20 and rsi < 70:
        signal = "BUY 🟢"
        sl = current_price - rule['sl']
        tp = current_price + rule['tp']
    elif current_price < ema_20 and rsi > 30:
        signal = "SELL 🔴"
        sl = current_price + rule['sl']
        tp = current_price - rule['tp']
    else:
        signal = "NEUTRAL / SIDEWAYS ⚪"
        sl = 0
        tp = 0

    return {
        'price': current_price,
        'rsi': round(rsi, 2),
        'ema_20': round(ema_20, 2),
        'ema_50': round(ema_50, 2),
        'signal': signal,
        'sl': sl,
        'tp': tp,
        'rule': rule
    }

# -------------------------------------------------------------
# 3. Telegram UI Handlers
# -------------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("⚡ M5 Signal", callback_data='sig_5m'), InlineKeyboardButton("⏱️ M15 Signal", callback_data='sig_15m')],
        [InlineKeyboardButton("📊 H1 Signal", callback_data='sig_1h'), InlineKeyboardButton("📈 H4 Signal", callback_data='sig_4h')],
        [InlineKeyboardButton("🏔️ D1 Signal", callback_data='sig_1d')],
        [InlineKeyboardButton("💰 Real Live Price & Fear/Greed", callback_data='live_price')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    welcome_text = (
        "<b>🔥 BTC/USDT Live Advanced Signal Bot</b>\n\n"
        "Timeframe ke mutabiq automatic TP/SL aur real-time Binance prices tracking!\n\n"
        "Niche button click karke analyze karein:"
    )
    await update.message.reply_text(welcome_text, parse_mode='HTML', reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Back to Menu Keyboard
    back_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Main Menu", callback_data='main_menu')]])

    if query.data == 'main_menu':
        keyboard = [
            [InlineKeyboardButton("⚡ M5 Signal", callback_data='sig_5m'), InlineKeyboardButton("⏱️ M15 Signal", callback_data='sig_15m')],
            [InlineKeyboardButton("📊 H1 Signal", callback_data='sig_1h'), InlineKeyboardButton("📈 H4 Signal", callback_data='sig_4h')],
            [InlineKeyboardButton("🏔️ D1 Signal", callback_data='sig_1d')],
            [InlineKeyboardButton("💰 Real Live Price & Fear/Greed", callback_data='live_price')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("<b>🔥 Main Menu: Choose Options</b>", parse_mode='HTML', reply_markup=reply_markup)

    elif query.data == 'live_price':
        df = get_live_btc_data('1m', limit=2)
        if df is not None:
            price = df['close'].iloc[-1]
            fng_val, fng_status = get_fear_and_greed()
            msg = (
                f"<b>⚡ BTC/USDT Live Price</b>\n\n"
                f"<b>Current Price:</b> ${price:,.2f}\n"
                f"<b>Fear & Greed Index:</b> {fng_val} ({fng_status})\n"
                f"<b>Source:</b> Binance Direct API"
            )
            await query.edit_message_text(text=msg, parse_mode='HTML', reply_markup=back_keyboard)

    elif query.data.startswith('sig_'):
        tf = query.data.split('_')[1]
        data = analyze_market(tf)

        if data:
            if data['sl'] > 0:
                msg = (
                    f"<b>{data['rule']['name']} Trade Setup</b>\n\n"
                    f"<b>BTC Price:</b> ${data['price']:,.2f}\n"
                    f"<b>Signal:</b> {data['signal']}\n"
                    f"<b>RSI (14):</b> {data['rsi']}\n"
                    f"<b>EMA 20/50:</b> ${data['ema_20']:,.0f} / ${data['ema_50']:,.0f}\n"
                    f"-----------------------------\n"
                    f"<b>🎯 Take Profit (TP):</b> ${data['tp']:,.2f} (+{data['rule']['tp']} pips)\n"
                    f"<b>🛑 Stop Loss (SL):</b> ${data['sl']:,.2f} (-{data['rule']['sl']} pips)\n"
                    f"<b>Risk/Reward Ratio:</b> 1:2+"
                )
            else:
                msg = (
                    f"<b>{data['rule']['name']} Trade Setup</b>\n\n"
                    f"<b>BTC Price:</b> ${data['price']:,.2f}\n"
                    f"<b>Status:</b> {data['signal']}\n"
                    f"<b>RSI (14):</b> {data['rsi']}\n\n"
                    f"💡 <i>Market range-bound hai, clear entry trigger ka wait karein.</i>"
                )
            await query.edit_message_text(text=msg, parse_mode='HTML', reply_markup=back_keyboard)

# -------------------------------------------------------------
# 4. Main Execution
# -------------------------------------------------------------
if __name__ == '__main__':
    app = Application.builder().token(TOKEN).build()
    app.add_handle
r(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("Bot is live & listening to Telegram...")
    app.run_polling()