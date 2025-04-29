import logging
from functools import reduce

import pandas as pd
from talib import abstract as  ta
import pandas_ta as pta
import numpy as np
from freqtrade.vendor.qtpylib import indicators as qtpylib
from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter

logger = logging.getLogger(__name__)

MINIMAL_ROI = {
    "60": 0.01,
    "30": 0.03,
    "20": 0.04,
    "0": 0.05
}
EXIT_PROFIT_ONLY = False
TIMEFRAME = '5m'
MINUS_DI = 0
ADX = 10
FALING_TEMA_PERIOD = 1
FAST_D = 70



class XGBoostClassifierStrategy(IStrategy):
    """
    This is a basic XGBoostClassifierStrategy based on a certain set of indicators and oscillators
    """
    INTERFACE_VERSION: int = 3
    # Minimal ROI designed for the strategy.
    # This attribute will be overridden if the config file contains "minimal_roi"
    minimal_roi =  MINIMAL_ROI

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

    startup_candle_count: int = 40
    can_short = False

    sell_rsi = IntParameter(low=50, high=100, default=70, space="sell", optimize=True, load=True)

    def informative_pairs(self):
        return []


    def feature_engineering_expand_all(
        self, dataframe: DataFrame, period: int, metadata: dict, **kwargs
    ) -> DataFrame:
        """
        *Only functional with FreqAI enabled strategies*
        This function will automatically expand the defined features on the config defined
        `indicator_periods_candles`, `include_timeframes`, `include_shifted_candles`, and
        `include_corr_pairs`. In other words, a single feature defined in this function
        will automatically expand to a total of
        `indicator_periods_candles` * `include_timeframes` * `include_shifted_candles` *
        `include_corr_pairs` numbers of features added to the model.

        All features must be prepended with `%` to be recognized by FreqAI internals.

        Access metadata such as the current pair/timeframe with:

        `metadata["pair"]` `metadata["tf"]`

        More details on how these config defined parameters accelerate feature engineering
        in the documentation at:

        https://www.freqtrade.io/en/latest/freqai-parameter-table/#feature-parameters

        https://www.freqtrade.io/en/latest/freqai-feature-engineering/#defining-the-features

        :param dataframe: strategy dataframe which will receive the features
        :param period: period of the indicator - usage example:
        :param metadata: metadata of current pair
        dataframe["%-ema-period"] = ta.EMA(dataframe, timeperiod=period)
        """
        stochrsi_result = ta.STOCHRSI(dataframe, timeperiod=period)
        dataframe["%-stochrsi-k-period"], dataframe["%-stochrsi-d-period"] = stochrsi_result["fastk"], stochrsi_result["fastd"]
        # TEMA - Triple Exponential Moving Average
        dataframe["%-tema-period"] = ta.TEMA(dataframe, timeperiod=period)


        # EMA - Exponential Moving Average
        dataframe['%-ema-period'] = ta.EMA(dataframe, timeperiod=period)

        return dataframe

    def feature_engineering_expand_basic(
        self, dataframe: DataFrame, metadata: dict, **kwargs
    ) -> DataFrame:
        """
        *Only functional with FreqAI enabled strategies*
        This function will automatically expand the defined features on the config defined
        `include_timeframes`, `include_shifted_candles`, and `include_corr_pairs`.
        In other words, a single feature defined in this function
        will automatically expand to a total of
        `include_timeframes` * `include_shifted_candles` * `include_corr_pairs`
        numbers of features added to the model.

        Features defined here will *not* be automatically duplicated on user defined
        `indicator_periods_candles`

        All features must be prepended with `%` to be recognized by FreqAI internals.

        Access metadata such as the current pair/timeframe with:

        `metadata["pair"]` `metadata["tf"]`

        More details on how these config defined parameters accelerate feature engineering
        in the documentation at:

        https://www.freqtrade.io/en/latest/freqai-parameter-table/#feature-parameters

        https://www.freqtrade.io/en/latest/freqai-feature-engineering/#defining-the-features

        :param dataframe: strategy dataframe which will receive the features
        :param metadata: metadata of current pair
        dataframe["%-pct-change"] = dataframe["close"].pct_change()
        dataframe["%-ema-200"] = ta.EMA(dataframe, timeperiod=200)
        """
        heikinashi = qtpylib.heikinashi(dataframe)
        dataframe['%-ha_open'] = heikinashi['open']
        dataframe['%-ha_close'] = heikinashi['close']
        dataframe['%-ha_high'] = heikinashi['high']
        dataframe['%-ha_low'] = heikinashi['low']

        dataframe["%-minus_di"] = ta.MINUS_DI(dataframe)


        # RSI
        dataframe["%-rsi"] = ta.RSI(dataframe)



        # we believe that volume and closing price is helpful for predicting next price
        dataframe["%-raw_volume"] = dataframe["volume"]
        dataframe["%-raw_price"] = dataframe["close"]

        dataframe['%-mean-volume'] = dataframe['volume'].rolling(12).mean()


        macd_results = ta.MACD(dataframe)
        dataframe["%-macd"], dataframe["%-macd-signal"], dataframe["%-macd-hist"] = macd_results["macd"], macd_results["macdsignal"], macd_results["macdhist"]
        dataframe["%-dpo"] = pta.dpo(dataframe["close"], lookahead=False)

        # ADX
        dataframe['%-slowadx'] = ta.ADX(dataframe, 35)

        # Commodity Channel Index: values Oversold:<-100, Overbought:>100
        dataframe['%-cci'] = ta.CCI(dataframe)




        # Slow Stoch
        slowstoch = ta.STOCHF(dataframe, 50)
        dataframe['%-slowfastd'] = slowstoch['fastd']
        dataframe['%-slowfastk'] = slowstoch['fastk']


        donchian_df = pta.donchian(dataframe["high"], dataframe["low"])
        if isinstance(donchian_df, pd.DataFrame):
            donchian_colnames = donchian_df.columns
            for donchian_colname in donchian_colnames:
                freq_colname = "%-" + donchian_colname
                dataframe[freq_colname] = donchian_df[donchian_colname]

        return dataframe

    def feature_engineering_standard(
        self, dataframe: DataFrame, metadata: dict, **kwargs
    ) -> DataFrame:
        """
        *Only functional with FreqAI enabled strategies*
        This optional function will be called once with the dataframe of the base timeframe.
        This is the final function to be called, which means that the dataframe entering this
        function will contain all the features and columns created by all other
        freqai_feature_engineering_* functions.

        This function is a good place to do custom exotic feature extractions (e.g. tsfresh).
        This function is a good place for any feature that should not be auto-expanded upon
        (e.g. day of the week).

        All features must be prepended with `%` to be recognized by FreqAI internals.

        Access metadata such as the current pair with:

        `metadata["pair"]`

        More details about feature engineering available:

        https://www.freqtrade.io/en/latest/freqai-feature-engineering

        :param dataframe: strategy dataframe which will receive the features
        :param metadata: metadata of current pair
        usage example: dataframe["%-day_of_week"] = (dataframe["date"].dt.dayofweek + 1) / 7
        """
        return dataframe

    def set_freqai_targets(self, dataframe: DataFrame, metadata: dict, **kwargs) -> DataFrame:
        """
        *Only functional with FreqAI enabled strategies*
        Required function to set the targets for the model.
        All targets must be prepended with `&` to be recognized by the FreqAI internals.

        Access metadata such as the current pair with:

        `metadata["pair"]`

        More details about feature engineering available:

        https://www.freqtrade.io/en/latest/freqai-feature-engineering

        :param dataframe: strategy dataframe which will receive the targets
        :param metadata: metadata of current pair
        usage example: dataframe["&-target"] = dataframe["close"].shift(-1) / dataframe["close"]
        """

        target_candles = dataframe["close"].shift(-self.freqai_info["feature_parameters"]["label_period_candles"])
        is_bigger_mask = target_candles > dataframe["close"]
        dataframe['&s-up_or_down'] =  np.where(is_bigger_mask, "up", "down")

        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # All indicators must be populated by feature_engineering_*() functions

        # the model will return all labels created by user in `set_freqai_targets()`
        # (& appended targets), an indication of whether or not the prediction should be accepted,
        # the target mean/std values for each of the labels created by user in
        # `set_freqai_targets()` for each training period.




        dataframe = self.freqai.start(dataframe, metadata, self)

        # heiknashi

        heikinashi = qtpylib.heikinashi(dataframe)
        dataframe['ha_open'] = heikinashi['open']
        dataframe['ha_close'] = heikinashi['close']
        dataframe['ha_high'] = heikinashi['high']
        dataframe['ha_low'] = heikinashi['low']

        # Minus Directional Indicator / Movement
        dataframe["minus_di"] = ta.MINUS_DI(dataframe)


        # RSI
        dataframe["rsi"] = ta.RSI(dataframe)


        # TEMA - Triple Exponential Moving Average
        dataframe["tema"] = ta.TEMA(dataframe, timeperiod=9)


        # EMA - Exponential Moving Average
        dataframe['ema5'] = ta.EMA(dataframe, timeperiod=5)
        dataframe['ema20'] = ta.EMA(dataframe, timeperiod=20)
        dataframe['ema50'] = ta.EMA(dataframe, timeperiod=50)
        dataframe['ema100'] = ta.EMA(dataframe, timeperiod=100)

        dataframe['adx'] = ta.ADX(dataframe)


        # Stoch
        stoch = ta.STOCHF(dataframe, 5)
        dataframe['fastd'] = stoch['fastd']
        dataframe['fastk'] = stoch['fastk']



        return dataframe

    def populate_entry_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        enter_long_conditions = [
            df["do_predict"] == 1,
            df['&s-up_or_down'] == "up",
        ]

        if enter_long_conditions:
            df.loc[
                reduce(lambda x, y: x & y, enter_long_conditions), ["enter_long", "enter_tag"]
            ] = (1, "long")

        enter_short_conditions = [
            df["do_predict"] == 1,
            df['&s-up_or_down'] == "down",
        ]

        if enter_short_conditions:
            df.loc[
                reduce(lambda x, y: x & y, enter_short_conditions), ["enter_short", "enter_tag"]
            ] = (1, "short")

        return df

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
                    (qtpylib.crossed_above(dataframe["rsi"], self.sell_rsi.value))
                    | (qtpylib.crossed_above(dataframe["fastd"], FAST_D))
                )
                & (dataframe["tema"] < dataframe["tema"].shift(FALING_TEMA_PERIOD))
                | (dataframe["adx"] > ADX)
                & (dataframe["minus_di"] > MINUS_DI)

            ) ,
            'exit_long'] = 1
        return dataframe

    # def confirm_trade_entry(
    #     self,
    #     pair: str,
    #     order_type: str,
    #     amount: float,
    #     rate: float,
    #     time_in_force: str,
    #     current_time,
    #     entry_tag,
    #     side: str,
    #     **kwargs,
    # ) -> bool:
    #     df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
    #     last_candle = df.iloc[-1].squeeze()
    #
    #     if side == "long":
    #         if rate > (last_candle["close"] * (1 + 0.0025)):
    #             return False
    #     else:
    #         if rate < (last_candle["close"] * (1 - 0.0025)):
    #             return False
    #
    #     return True


