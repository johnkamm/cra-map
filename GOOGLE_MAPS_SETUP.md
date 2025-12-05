# Google Maps API Setup Guide

## Why Use Google Maps?

- **Better Accuracy**: ~95-98% success rate vs ~60% with free Nominatim
- **Cost Effective**: Pay only for addresses that fail free geocoding (~40% of total)
- **Estimated Cost**: $14 for ~2,800 addresses (vs $35 for all 7,000)

## Step 1: Get a Google Maps API Key

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing)
3. Enable the **Geocoding API**:
   - Navigate to "APIs & Services" > "Library"
   - Search for "Geocoding API"
   - Click "Enable"
4. Create API Key:
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "API Key"
   - Copy your API key (keep it secret!)

## Step 2: Set Up Billing

1. In Google Cloud Console, go to "Billing"
2. Add a payment method
3. **Important**: Set a budget alert to avoid surprise charges
   - Recommended: $20 limit
   - Expected cost for this project: ~$14

## Step 3: Use the API Key

### Option A: Command Line (Recommended)
```bash
python geocode_addresses.py --google-api-key YOUR_API_KEY_HERE
```

### Option B: Environment Variable
```bash
# Windows
set GOOGLE_MAPS_API_KEY=YOUR_API_KEY_HERE
python geocode_addresses.py --google-api-key %GOOGLE_MAPS_API_KEY%

# Mac/Linux
export GOOGLE_MAPS_API_KEY=YOUR_API_KEY_HERE
python geocode_addresses.py --google-api-key $GOOGLE_MAPS_API_KEY
```

## How Hybrid Geocoding Works

1. **First**: Try free Nominatim (OpenStreetMap) - **0 cost**
2. **If that fails**: Try Google Maps API - **~$0.005 per request**
3. **Final fallback**: City-level geocoding with Nominatim - **0 cost**

## Expected Results

Without Google API:
- ~60% exact addresses
- ~40% city-level approximations

With Google API:
- ~95-98% exact addresses
- ~2-5% city-level approximations
- **Cost**: ~$14 total

## Cost Breakdown

- Google charges $5 per 1,000 requests
- Expected failures from Nominatim: ~2,800 addresses (40%)
- Cost: 2,800 / 1,000 × $5 = **$14**

## Security Best Practices

1. **Restrict API Key** (in Google Cloud Console):
   - Go to API key settings
   - Add "Application restrictions" > "IP addresses"
   - Add your IP address
2. **Never commit API key to Git**
3. **Delete API key when done** (if not using for monthly updates)

## Testing First

**Highly Recommended**: Test with sample data first:
```bash
python geocode_addresses.py --test --limit 50 --google-api-key YOUR_KEY
```

This will:
- Test 50 addresses
- Cost: ~$0.10
- Show you the improvement in accuracy
- Verify API key works

## Monitoring Costs

1. Go to Google Cloud Console > Billing
2. View current charges in real-time
3. Check "Reports" for detailed usage

## Alternative: Run Without Google API

If you prefer to avoid costs entirely:
```bash
python geocode_addresses.py
```

This uses only free Nominatim, with ~40% falling back to city-level locations.
