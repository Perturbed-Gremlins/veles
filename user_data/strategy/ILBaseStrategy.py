# --- Do not remove these libs ---
from freqtrade.strategy import IStrategy
from pandas import DataFrame
# --------------------------------

import talib.abstract as ta

from freqtrade.vendor import qtpyrlib, qtpylib

"""
Не забудь апнуть populate_indicators
Параметры для прогона на бэктестах для проверки стратегии
"""
MINIMAL_ROI = {
    "60": 0.01,
    "30": 0.03,
    "20": 0.04,
    "0": 0.05
}
EXIT_PROFIT_ONLY = False
TIMEFRAME = '5m'
MIMUS_DI = 0
ADX = 10
FALING_TEMA_PERIOD = 1
FAST_D = 70

class Hikers(IStrategy):


    INTERFACE_VERSION: int = 3
    # Minimal ROI designed for the strategy.
    # This attribute will be overridden if the config file contains "minimal_roi"
    minimal_roi = MINIMAL_ROI

    # Optimal stoploss designed for the strategy
    # This attribute will be overridden if the config file contains "stoploss"
    stoploss = -0.10

    # Optimal timeframe for the strategy
    timeframe = '5m'

    # trailing stoploss
    trailing_stop = False
    trailing_stop_positive = 0.01
    trailing_stop_positive_offset = 0.02

    # run "populate_indicators" only for new candle
    process_only_new_candles = True

    # Experimental settings (configuration will overide these if set)
    use_exit_signal = True
    exit_profit_only = EXIT_PROFIT_ONLY
    ignore_roi_if_entry_signal = True

    # Optional order type mapping
    order_types = {
        'entry': 'limit',
        'exit': 'limit',
        'stoploss': 'market',
        'stoploss_on_exchange': False
    }

    def informative_pairs(self):
        return []

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Adds several different TA indicators to the given DataFrame

        Performance Note: For the best performance be frugal on the number of indicators
        you are using. Let uncomment only the indicator you are using in your strategies
        or your hyperopt configuration, otherwise you will waste your memory and CPU usage.
        """

        # ADX
        dataframe['adx'] = ta.ADX(dataframe)
        dataframe['slowadx'] = ta.ADX(dataframe, 35)

        # Commodity Channel Index: values Oversold:<-100, Overbought:>100
        dataframe['cci'] = ta.CCI(dataframe)

        # Stoch
        stoch = ta.STOCHF(dataframe, 5)
        dataframe['fastd'] = stoch['fastd']
        dataframe['fastk'] = stoch['fastk']
        dataframe['fastk-previous'] = dataframe.fastk.shift(1)
        dataframe['fastd-previous'] = dataframe.fastd.shift(1)

        # Slow Stoch
        slowstoch = ta.STOCHF(dataframe, 50)
        dataframe['slowfastd'] = slowstoch['fastd']
        dataframe['slowfastk'] = slowstoch['fastk']
        dataframe['slowfastk-previous'] = dataframe.slowfastk.shift(1)
        dataframe['slowfastd-previous'] = dataframe.slowfastd.shift(1)

        # EMA - Exponential Moving Average
        dataframe['ema5'] = ta.EMA(dataframe, timeperiod=5)

        dataframe['mean-volume'] = dataframe['volume'].rolling(12).mean()

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        :param dataframe: DataFrame
        :return: DataFrame with buy column
        """
        dataframe.loc[
            'enter_long'] = 1 # ToDo what say ML

        return dataframe

    def stoploss_from_absolute(
            stop_rate: float, current_rate: float, is_short: bool = False, leverage: float = 1.0
    ) -> float:
        """
        Given current price and desired stop price, return a stop loss value that is relative to current
        price.

        The requested stop can be positive for a stop above the open price, or negative for
        a stop below the open price. The return value is always >= 0.

        Returns 0 if the resulting stop price would be above the current price.

        :param stop_rate: Stop loss price.
        :param current_rate: Current asset price.
        :param is_short: When true, perform the calculation for short instead of long
        :param leverage: Leverage to use for the calculation
        :return: Positive stop loss value relative to current price
        """

        # formula is undefined for current_rate 0, return maximum value
        if current_rate == 0:
            return 1

        stoploss = 1 - (stop_rate / current_rate)
        if is_short:
            stoploss = -stoploss
        return max(min(stoploss, 1.0), 0.0) * leverage


    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the sell signal for the given dataframe
        :param dataframe: DataFrame
        :return: DataFrame with buy column
        """
        dataframe.loc[
            (
                qtpylib.crossed_above(dataframe['ema50'], dataframe['ema100'])
                &(dataframe['ha_close'] < dataframe['ema20'])
                &(dataframe['ha_open'] > dataframe['ha_close'])
                |
                (
                    (qtpylib.crossed_above(dataframe["%-rsi"], self.sell_rsi.value))
                    | (qtpylib.crossed_above(dataframe["%-fastd"], FAST_D))
                )
                & (dataframe["tema"] < dataframe["tema"].shift(FALING_TEMA_PERIOD))
                | (dataframe["adx"] > ADX)
                & (dataframe["minus_di"] > MIMUS_DI)

            ),
            'exit_long'] = 1
        return dataframe



