#!/usr/bin/env python3
# generate_secrets.py
import secrets
import argparse

def generate_secret(length=32):
    return secrets.token_hex(length)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate secure secrets for production")
    parser.add_argument("--jwt", action="store_true", help="Generate JWT secret")
    parser.add_argument("--db", action="store_true", help="Generate DB password")
    parser.add_argument("--redis", action="store_true", help="Generate Redis password")
    parser.add_argument("--all", action="store_true", help="Generate all secrets")
    parser.add_argument("--length", type=int, default=32, help="Secret length (default: 32)")
    
    args = parser.parse_args()
    
    if args.all or args.jwt:
        print(f"JWT_SECRET_KEY={generate_secret(args.length)}")
    
    if args.all or args.db:
        print(f"DB_PASSWORD={generate_secret(16)}")
    
    if args.all or args.redis:
        print(f"REDIS_PASSWORD={generate_secret(16)}")