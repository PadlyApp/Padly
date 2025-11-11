cd backend

python3 -m venv venv

pip install -r requirements.txt

-----------------------------------
WINDOWS: .\venv\Scripts\activate
MAC/LINUX: venv/bin/activate
-----------------------------------

uvicorn app.main:app --reload

-----------------------------------

## 📦 Data Parser for Algorithms

**NEW**: Parse mock data from Supabase into JSON objects for algorithms!

### Quick Start
```bash
# Test the data parser
python -m app.scripts.test_data_parser

# Run usage examples
python -m app.scripts.example_usage
```

### Access via API
```bash
# Get all parsed listings
curl http://localhost:8000/api/matches/data/listings

# Get all parsed groups
curl http://localhost:8000/api/matches/data/groups

# Get both
curl http://localhost:8000/api/matches/data/all
```

### Documentation
- 📖 **Quick Start**: See [QUICK_REFERENCE.md](QUICK_REFERENCE.md)
- 📚 **Full Details**: See [app/services/DATA_PARSER_README.md](app/services/DATA_PARSER_README.md)
- 📋 **Implementation**: See [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)
- ✅ **Checklist**: See [CHECKLIST.md](CHECKLIST.md)

### What You Get
- ✅ **Listings JSON**: All listings properly formatted
- ✅ **Groups JSON**: All roommate groups with members
- ✅ **API Endpoints**: Access data via HTTP
- ✅ **Test Scripts**: Verify everything works
- ✅ **Examples**: 8 usage patterns included

