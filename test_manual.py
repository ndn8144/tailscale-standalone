#!/usr/bin/env python3
"""
Manual testing script - run this to verify everything works
"""

import asyncio
import sys
from src.installer_builder import InstallerBuilder

async def main():
    print("🧪 Manual Testing Script")
    print("=" * 40)
    
    builder = InstallerBuilder()
    
    try:
        print("1. Testing API connection...")
        token = await builder.api.get_access_token()
        print(f"✅ Token obtained: {token[:20]}...")
        
        print("\\n2. Testing auth key creation...")
        auth_key = await builder.create_auth_key(
            tags=["tag:test"],
            expires_days=1,
            description="Manual test key"
        )
        print(f"✅ Auth key created: {auth_key['id']}")
        
        print("\\n3. Testing MSI download...")
        msi_data = builder.download_tailscale_msi()
        print(f"✅ MSI downloaded: {len(msi_data) / (1024*1024):.2f} MB")
        
        print("\\n4. Testing build process...")
        result = await builder.build_installer(
            tags=["tag:test"],
            expires_days=1,
            output_name="test-build",
            description="Manual test build"
        )
        
        print(f"✅ Build successful!")
        print(f"📁 File: {result['exe_path']}")
        print(f"📊 Size: {result['build_info']['exe_size_mb']} MB")
        
        # Ask if user wants to test the installer
        response = input("\\n🔧 Test the installer? (y/N): ").lower()
        if response == 'y':
            print("⚠️  Make sure to run the generated .exe as Administrator!")
            print("⚠️  This will install Tailscale on this machine!")
            confirm = input("Continue? (y/N): ").lower()
            if confirm == 'y':
                import subprocess
                subprocess.run([str(result['exe_path'])], shell=True)
        
        print("\\n✅ All tests passed!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return 1
    
    finally:
        builder.cleanup_temp_files()
    
    return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))