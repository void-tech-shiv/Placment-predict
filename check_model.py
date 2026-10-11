import joblib

print("=" * 60)

features = joblib.load("saved_models/feature_columns.pkl")

print("Feature Columns:")
print(features)

print("\nType:")
print(type(features))

print("\nLength:")
print(len(features))

print("=" * 60)

encoders = joblib.load("saved_models/label_encoders.pkl")

print("Encoder Keys:")
print(encoders.keys())

print("=" * 60)