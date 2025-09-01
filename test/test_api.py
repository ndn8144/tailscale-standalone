import pytest
import asyncio
from src.tailscale_api import TailscaleAPI

@pytest.fixture
def api():
    return TailscaleAPI()

@pytest.mark.asyncio
async def test_get_access_token(api):
    token = await api.get_access_token()
    assert token is not None
    assert len(token) > 20

@pytest.mark.asyncio
async def test_create_auth_key(api):
    key = await api.create_auth_key(
        tags=["tag:test"],
        expires_days=1,
        description="Test key"
    )
    
    assert 'key' in key
    assert 'id' in key
    assert key['key'].startswith('tskey-auth-')

@pytest.mark.asyncio 
async def test_list_devices(api):
    devices = await api.list_devices()
    assert 'devices' in devices
    assert isinstance(devices['devices'], list)