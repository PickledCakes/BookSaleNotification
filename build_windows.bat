@echo off
setlocal
py -m pip install --upgrade pip
py -m pip install -r requirements.txt pyinstaller
pyinstaller --noconfirm --clean BookSaleNotification.spec
echo.
echo Build complete: dist\Book Sale Notification\
pause
