import pytest
import asyncio
import tempfile
from pathlib import Path
from src.installer_builder import InstallerBuilder

@pytest.mark.asyncio
async def test_build_installer():
    builder = InstallerBuilder()
    
    # Override build dir for test
    with tempfile.TemporaryDirectory() as temp_dir:
        builder.build_dir = Path(temp_dir)
        builder.temp_dir = Path(temp_dir) / "temp"
        
        result = await builder.build_installer(
            tags=["tag:test"],
            expires_days=1,
            output_name="test-installer"
        )
        
        assert result['exe_path'].exists()
        assert result['exe_path'].stat().st_size > 1024 * 1024  # > 1MB
        assert 'auth_key' in result
        assert result['auth_key']['key'].startswith('tskey-auth-')