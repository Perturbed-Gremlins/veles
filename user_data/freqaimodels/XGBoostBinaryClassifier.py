import logging
from typing import Any

import numpy as np
import numpy.typing as npt
import pandas as pd
from pandas import DataFrame
from pandas.api.types import is_integer_dtype
from sklearn.preprocessing import LabelEncoder
from xgboost import XGBClassifier

from freqtrade.freqai.base_models.BaseClassifierModel import BaseClassifierModel
from freqtrade.freqai.data_kitchen import FreqaiDataKitchen


logger = logging.getLogger(__name__)


TRAIN_FEATURES_KEY = "train_features"
TRAIN_LABELS_KEY = "train_labels"
TEST_FEATURES_KEY = "test_features"
TEST_LABELS_KEY = "test_labels"


class XGBoostClassifier(BaseClassifierModel):
    """
    User created prediction model. The class inherits IFreqaiModel, which
    means it has full access to all Frequency AI functionality. Typically,
    users would use this to override the common `fit()`, `train()`, or
    `predict()` methods to add their custom data handling tools or change
    various aspects of the training that cannot be configured via the
    top level config.json file.
    """

    @staticmethod
    def convert_data_to_sk(features_df: pd.DataFrame, labels_df: pd.DataFrame):
        """
        This function acts as a transformer of data dictionary format (features and labels) to the
        sk compatible format. Also converts the labels to numeric format if it's not already
        """

        # getting the pure numpy arrays of features
        features_array = features_df.to_numpy()

        # here we need to collapse the one-sized columns
        labels_array_collapsed = labels_df.to_numpy()[:, 0]

        le = LabelEncoder()

        # enable conversion if the target non numeric (integer)
        if not is_integer_dtype(labels_array_collapsed):
            numeric_labels = le.fit_transform(labels_array_collapsed)
            labels_array_collapsed = pd.Series(numeric_labels, dtype="int64")

        return features_array,labels_array_collapsed


    def fit(self, data_dictionary: dict, dk: FreqaiDataKitchen, **kwargs) -> Any:
        """
        User sets up the training and test data to fit their desired model here
        :param data_dictionary: the dictionary holding all data for train, test,
            labels, weights
        :param dk: The datakitchen object for the current coin/model
        """

        train_features_df = data_dictionary[TRAIN_FEATURES_KEY]
        train_labels_df = data_dictionary[TRAIN_LABELS_KEY]

        X, y = self.convert_data_to_sk(train_features_df, train_labels_df)
        # checking the configuration of a test size, if none, then setting appropriate kw
        # otherwise form same set but for eval set
        conf_test_size = self.freqai_info.get("data_split_parameters", {}).get("test_size", 0.1)
        if conf_test_size == 0:
            eval_set = None
        else:
            test_features_df = data_dictionary[TEST_FEATURES_KEY]
            test_labels_df = data_dictionary[TEST_LABELS_KEY]

            test_features, test_labels = self.convert_data_to_sk(test_features_df, test_labels_df)

            eval_set = [(test_features, test_labels)]

        train_weights = data_dictionary["train_weights"]

        init_model = self.get_init_model(dk.pair)


        self.model_training_parameters["objective"]="binary:logistic"
        self.model_training_parameters["eval_metric"]="auc"
        model = XGBClassifier(**self.model_training_parameters )

        model.fit(X=X, y=y, eval_set=eval_set, sample_weight=train_weights, xgb_model=init_model)

        return model

    def predict(
        self, unfiltered_df: DataFrame, dk: FreqaiDataKitchen, **kwargs
    ) -> tuple[DataFrame, npt.NDArray[np.int_]]:
        """
        Filter the prediction features data and predict with it.
        :param unfiltered_df: Full dataframe for the current backtest period.
        :return:
        :pred_df: dataframe containing the predictions
        :do_predict: np.array of 1s and 0s to indicate places where freqai needed to remove
        data (NaNs) or felt uncertain about data (PCA and DI index)
        """
        (pred_df, dk.do_predict) = super().predict(unfiltered_df, dk, best_iteration=True, **kwargs)
        le = LabelEncoder()
        label = dk.label_list[0]
        labels_before = list(dk.data["labels_std"].keys())
        labels_after = le.fit_transform(labels_before).tolist()
        pred_df[label] = le.inverse_transform(pred_df[label])
        pred_df = pred_df.rename(
            columns={labels_after[i]: labels_before[i] for i in range(len(labels_before))}
        )
        return (pred_df, dk.do_predict)
