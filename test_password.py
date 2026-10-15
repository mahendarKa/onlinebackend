from app.utils.security import hash_password, verify_password

password = "admin123"

hashed = hash_password(password)

print(hashed)
print("verify:", verify_password(password, hashed))