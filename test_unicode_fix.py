#!/usr/bin/env python3
"""
Test script to verify Unicode encoding fix
"""

import sys
import os

def test_unicode_output():
    """Test Unicode characters that were causing issues"""
    
    print("Testing Unicode characters...")
    
    # Test the specific emoji that was causing the error
    try:
        print("🚀")  # This was the problematic character
        print("✅")  # Check mark
        print("❌")  # X mark
        print("📥")  # Download
        print("🔨")  # Hammer
        print("🎉")  # Party
        print("💡")  # Light bulb
        print("🛡️")  # Shield
        print("📝")  # Memo
        print("🔧")  # Wrench
        print("📋")  # Clipboard
        print("🖥️")  # Desktop computer
        print("🌐")  # Globe
        print("🔄")  # Refresh
        print("⚠️")  # Warning
        print("👉")  # Pointing right
        
        print("\nAll Unicode characters printed successfully!")
        return True
        
    except UnicodeEncodeError as e:
        print(f"\nUnicode encoding error: {e}")
        return False
    except Exception as e:
        print(f"\nOther error: {e}")
        return False

def test_console_encoding():
    """Test console encoding"""
    print(f"\nConsole encoding: {sys.stdout.encoding}")
    print(f"Default encoding: {sys.getdefaultencoding()}")
    
    # Test if we can write to a file with UTF-8
    try:
        with open("test_unicode.txt", "w", encoding="utf-8") as f:
            f.write("🚀 Test Unicode characters\n")
            f.write("✅ Success\n")
            f.write("❌ Error\n")
        print("UTF-8 file write successful")
        
        # Clean up
        os.remove("test_unicode.txt")
        return True
    except Exception as e:
        print(f"File write error: {e}")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("Unicode Encoding Test")
    print("=" * 50)
    
    unicode_ok = test_unicode_output()
    file_ok = test_console_encoding()
    
    print("\n" + "=" * 50)
    if unicode_ok and file_ok:
        print("✅ All tests passed - Unicode fix should work")
    else:
        print("❌ Some tests failed - may still have encoding issues")
    print("=" * 50)
