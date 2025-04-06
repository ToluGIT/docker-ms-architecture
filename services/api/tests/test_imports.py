import sys
print("Python path:", sys.path)

try:
    import app
    print("Successfully imported app module")
    import app.main
    print("Successfully imported app.main module")
except ImportError as e:
    print("Import error:", e)