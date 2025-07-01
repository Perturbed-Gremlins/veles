import logging
from pathlib import Path

import shap
import xgboost.callback
from joblib.externals import cloudpickle
from xgboost.callback import _Model


logger = logging.getLogger(__name__)


class ShapleyCallback(xgboost.callback.TrainingCallback):
    """
    XGBoost callback for computing and saving SHAP values and explainer objects.
    
    Integrates with FreqAI's model saving architecture to store SHAP artifacts
    alongside model files for later analysis.
    """

    def __init__(self, prediction_features, data_path, model_filename):
        super().__init__()
        
        self.prediction_features = prediction_features
        self.data_path = Path(data_path)
        self.model_filename = model_filename

    def after_training(self, model: _Model) -> _Model:
        """
        Called after XGBoost model training completes.
        Computes SHAP values and saves explainer objects.
        """
        logger.info(f"Computing SHAP values for model {self.model_filename}")
        
        # Create SHAP explainer
        explainer = shap.TreeExplainer(model)
        
        # Compute SHAP values and explanations
        shap_values = explainer.shap_values(self.prediction_features)
        explanation = explainer(self.prediction_features)
        
        # Save explainer object using cloudpickle (consistent with FreqAI)
        explainer_path = self.data_path / f"{self.model_filename}_shap_explainer.pkl"
        with explainer_path.open("wb") as fp:
            cloudpickle.dump(explainer, fp)
        logger.info(f"SHAP explainer saved to: {explainer_path}")
        
        # Save SHAP values as pickle for later analysis
        shap_values_path = self.data_path / f"{self.model_filename}_shap_values.pkl"
        with shap_values_path.open("wb") as fp:
            cloudpickle.dump(shap_values, fp)
        logger.info(f"SHAP values saved to: {shap_values_path}")
        
        # Save explanation object
        explanation_path = self.data_path / f"{self.model_filename}_shap_explanation.pkl"
        with explanation_path.open("wb") as fp:
            cloudpickle.dump(explanation, fp)
        logger.info(f"SHAP explanation saved to: {explanation_path}")
        
        return model