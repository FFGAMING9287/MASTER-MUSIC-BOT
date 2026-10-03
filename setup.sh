#!/bin/bash

echo "========================================"
echo "Installing Termux Packages & Dependencies"
echo "========================================"
pkg update && pkg upgrade -y
pkg install python ffmpeg git curl rust binutils make clang -y

echo "Installing Python Libraries..."

clear
echo "========================================"
echo "    ˹ꜰꜰɢᴀᴍɪɴɢ ꭙ ᴍᴜꜱɪᴄ ʙᴏᴛ !! Setup          "
echo "========================================"
echo "Niche apni details fill karein:"
echo ""

read -p "Enter API_ID (Required): " api_id
read -p "Enter API_HASH (Required): " api_hash
read -p "Enter Pyrogram SESSION string (Required): " session
read -p "Enter BOT_TOKEN (Optional, skip karne ke liye Enter dabayein): " bot_token
read -p "Enter SUDOERS IDs (Optional, space dekar dalein): " sudoers

echo "Generating .env file..."
echo "API_ID='$api_id'" > .env
echo "API_HASH='$api_hash'" >> .env
echo "SESSION='$session'" >> .env
echo "BOT_TOKEN='$bot_token'" >> .env
echo "SUDOERS='$sudoers'" >> .env
echo "PREFIX='!'" >> .env
echo "LANGUAGE='en'" >> .env
echo "QUALITY='high'" >> .env
echo "STREAM_MODE='audio'" >> .env
echo "ADMINS_ONLY='False'" >> .env

echo "========================================"
echo "Setup Complete! Starting Bot..."
echo "========================================"

python main.py
