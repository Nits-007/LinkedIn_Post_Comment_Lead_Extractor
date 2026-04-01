To run the project :
(Make to sure to have Python3 installed)

1. Clone the repository: git clone https://github.com/Nits-007/LinkedIn_Post_Comment_Lead_Extractor.git
2. Move to the project folder: cd LinkedIn_Post_Comment_Lead_Extractor
3. Make virtual Environment: python -m venv venv
4. Activate the virtual environment: venv\Scripts\activate
5. Install the libraries: pip install -r requirements.txt
6. Install playwright browsers: playwright install chromium
7. Run the project: python main.py
8. Now LinkedIn login page will get opened in a new window.
9. Enter your credentials to login
10. Enter the url of the post in the CLI and press Enter
11. Wait for some time (depends on the internet connection and number of comments on the post).
12. The scraped comments along with the necessary information like time, post url, commenter name, commenter profile url, comment and email adress (if available) will be stored in an excel sheet inside the output folder.

Demo Video Drive Link: 
