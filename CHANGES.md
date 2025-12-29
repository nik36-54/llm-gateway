# Changes Summary

## Provider Changes

### Removed
- **Anthropic** provider has been removed

### Added/Updated
- **HuggingFace** provider added with support for:
  - Llama-3 (`meta-llama/Meta-Llama-3-8B-Instruct`)
  - Mixtral (`mistralai/Mixtral-8x7B-Instruct-v0.1`)
  - Qwen (`Qwen/Qwen2-7B-Instruct`)

### Current Providers
1. **OpenAI** - Fast, reliable baseline (GPT-3.5, GPT-4)
2. **DeepSeek** - Cheapest option for cost control
3. **HuggingFace** - Open-source models (Llama-3, Mixtral, Qwen)

## Database Changes

- Updated to use **Supabase PostgreSQL** instead of local PostgreSQL
- Connection string format: `postgresql://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres`

## Configuration Changes

### New Environment Variables
- `HUGGINGFACE_API_KEY` - Required for HuggingFace Inference API

### Removed
- `ANTHROPIC_API_KEY` - No longer needed

### Updated
- `DATABASE_URL` - Now expects Supabase connection string

## Routing Logic Updates

- `task="reasoning"` now routes to HuggingFace (instead of Anthropic)
- HuggingFace models are selected via the `model` parameter in requests
- Fallback chain: OpenAI → DeepSeek → HuggingFace

## Cost Tracking Updates

- HuggingFace models are tracked as $0.00 (free tier)
- Updated provider detection logic to recognize HuggingFace models

## Files Changed

### Added
- `app/providers/huggingface.py` - HuggingFace provider adapter
- `SETUP_GUIDE.md` - Comprehensive setup instructions
- `CHANGES.md` - This file

### Removed
- `app/providers/anthropic.py` - Anthropic provider (removed)

### Modified
- `app/config.py` - Updated API keys and database URL
- `app/routing/rules.py` - Updated provider lists
- `app/routing/router.py` - Updated routing logic
- `app/cost/tracker.py` - Updated pricing and provider detection
- `docker-compose.yml` - Updated environment variables
- `README.md` - Updated documentation
- `tests/` - Updated all tests to use HuggingFace

## Migration Notes

If you're upgrading from the previous version:

1. **Update your `.env` file**:
   - Remove `ANTHROPIC_API_KEY`
   - Add `HUGGINGFACE_API_KEY`
   - Update `DATABASE_URL` to your Supabase connection string

2. **Get HuggingFace API key**:
   - Sign up at https://huggingface.co
   - Create a token at https://huggingface.co/settings/tokens
   - Add to `.env` as `HUGGINGFACE_API_KEY=hf_your-token`

3. **Update Supabase connection**:
   - Create a Supabase project at https://supabase.com
   - Get connection string from Settings → Database
   - Update `DATABASE_URL` in `.env`

4. **Run database migrations** (if needed):
   ```bash
   alembic upgrade head
   ```

5. **Test the changes**:
   ```bash
   pytest  # Run tests
   ```

## Breaking Changes

- API keys using Anthropic provider will no longer work
- Existing routing rules that used Anthropic will now use HuggingFace
- Database connection string format may need updating for Supabase

