import os
import numpy as np
import onnxruntime as ort

N_FEATURES = 7


def model_fn(model_dir):
    path = os.path.join(model_dir, "model.onnx")
    return ort.InferenceSession(path, providers=["CPUExecutionProvider"])


def predict_fn(input_data, session):
    X = np.asarray(input_data, dtype=np.float32).reshape(-1, N_FEATURES)
    input_name = session.get_inputs()[0].name
    prediction = session.run(None, {input_name: X})[0]
    return prediction.reshape(-1)