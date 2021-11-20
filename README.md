# Not-pidor-bot
Open source version of a telegram bot pidorbot

# Installation
Required MySQL db.

```
pip3 install mysql-connector-python python-telegram-bot PyYAML --upgrade
sudo apt tesseract-ocr tesseract-ocr-rus 
pip3 install pytesseract opencv-python --upgrade
git clone https://github.com/NatoshiSKMT/not-pidor-bot.git
cd not-pidor-bot/
```

Create the configuration file and setup your MySQL database connection and telegram token.
```
cp config.yml.example config.yml && nano config.yml
```

```
python3 main.py
```

# Reactions where
end/full/begin/any
