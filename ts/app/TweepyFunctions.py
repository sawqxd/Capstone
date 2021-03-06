import tweepy 
import json
import pymongo
from pymongo import MongoClient
import re
from datetime import datetime 
from datetime import timedelta
from .Credentials import access_key, access_secret, consumer_key, consumer_secret, database_connect
from nltk.corpus import stopwords
from nltk.stem import SnowballStemmer


stop_words = ['i', 'me', 'my', 'myself', 'we', 'our', 'ours', 'ourselves', 'you', "you're", "you've", "you'll", "you'd", 'your', 'yours', 'yourself', 'yourselves', 'he', 'him', 'his', 'himself', 'she', "she's", 'her', 'hers', 'herself', 'it', "it's", 'its', 'itself', 'they', 'them', 'their', 'theirs', 'themselves', 'what', 'which', 'who', 'whom', 'this', 'that', "that'll", 'these', 'those', 'am', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'having', 'do', 'does', 'did', 'doing', 'a', 'an', 'the', 'and', 'but', 'if', 'or', 'because', 'as', 'until', 'while', 'of', 'at', 'by', 'for', 'with', 'about', 'against', 'between', 'into', 'through', 'during', 'before', 'after', 'above', 'below', 'to', 'from', 'up', 'down', 'in', 'out', 'on', 'off', 'over', 'under', 'again', 'further', 'then', 'once', 'here', 'there', 'when', 'where', 'why', 'how', 'all', 'any', 'both', 'each', 'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very', 's', 't', 'can', 'will', 'just', 'don', "don't", 'should', "should've", 'now', 'd', 'll', 'm', 'o', 're', 've', 'y', 'ain', 'aren', "aren't", 'couldn', "couldn't", 'didn', "didn't", 'doesn', "doesn't", 'hadn', "hadn't", 'hasn', "hasn't", 'haven', "haven't", 'isn', "isn't", 'ma', 'mightn', "mightn't", 'mustn', "mustn't", 'needn', "needn't", 'shan', "shan't", 'shouldn', "shouldn't", 'wasn', "wasn't", 'weren', "weren't", 'won', "won't", 'wouldn', "wouldn't"]


RATE_ERROR = 0 
SEARCH_ERROR = 1
# stop_words = stopwords.words("english")
stemmer = SnowballStemmer("english")
TWEET_CLEANING_RE = r'@\S+|https?:\S+|http?:\S|[^A-Za-z0-9]+'


#returns all tweets tweeted in the past year by given username
def get_users_tweets(username): 
    auth = tweepy.OAuthHandler(consumer_key, consumer_secret) 
    auth.set_access_token(access_key, access_secret) 

    api = tweepy.API(auth) 

    # gets the current time and subtracts 1 year to find the end time
    current_time = datetime.now()
    end_time = current_time - timedelta(days=365)

    temp = []
    # attempts to get users tweets, if user does not exist or api call fails will return empty array 
    try:
         # gets first 200 tweets
        tweets = api.user_timeline(screen_name=username, 
                                   count = 200,
                                   tweet_mode="extended"
                                   ) 
        
         # if there are no tweets for the user, return empty array
        if not tweets:
            return []
            
        # creates array to hold all of the tweets and appends the exsiting tweets array to it
        all_tweets = []
        all_tweets.extend(tweets)
         # gets the id of the last tweet 
        oldest_id = tweets[-1].id

        # while the time of tweet of the last tweet in the array is more than the end time
        while tweets[-1].created_at > end_time:
            # gets the next 200 tweets starting at the last id
            tweets = api.user_timeline(screen_name=username, 
                           count=200,
                           max_id = oldest_id - 1, 
                           tweet_mode="extended"
                           )
            # if there are no more tweets, break the loop 
            if len(tweets) == 0:
                break
            # sets the oldest_id to the id of the last tweet    
            oldest_id = tweets[-1].id
            # adds the tweets to the all_tweets array
            all_tweets.extend(tweets)
            
    except tweepy.TweepError as err:
         # returns error if rate limit is exceeded
        if err.reason.find("status code = 429") > -1:
           return RATE_ERROR   
        #returns error if any other error, username doesnt exist, invalid syntax, user is private, no tweets in past year
        return SEARCH_ERROR
    
    for tweet in all_tweets:
        # need to do another check because the code could enter the loop but only 5 more tweets were in the last year
        if tweet.created_at > end_time:
            # extracts just the text
            temp.append(tweet.full_text)

    # returns array of tweets if sucessful
    result = {"tweet": temp}
    return result
    


# returns 3200 most recent tweets in the past week for given hashtag
def get_hashtag_tweets(hashtag):
    auth = tweepy.OAuthHandler(consumer_key, consumer_secret) 
    auth.set_access_token(access_key, access_secret) 
    # create api call 
    api = tweepy.API(auth ) 

    tweets = []
    try:
        #gets 100 tweets at a time until there are 3200 total
        for tweet in tweepy.Cursor(api.search,q="#"+hashtag,
                               count=100,
                               lang="en",
                               tweet_mode="extended"
                               ).items(3200):
            #appends the tweets to the arry 
            tweets.append(tweet.full_text)
    
    
    except tweepy.TweepError as err:
         # returns error if rate limit is exceeded
        if err.reason.find("status code = 429") > -1:
           return RATE_ERROR   
        #returns error if any other error, hashtag doesnt exist, invalid syntax, no tweets avalible in past 7 days, ect
        return SEARCH_ERROR


    # if sucessful returns tweets 
    if tweets:
        result = {"tweet": tweets}
        return result
    return []



#runs preprocessing algorithm on tweets
def preprocess(tweet, stem=False):
    """Preprocesses one tweet"""
    tweet = re.sub(TWEET_CLEANING_RE, ' ', str(tweet).lower()).strip()
    tokens = []
    for token in tweet.split():
        if token not in stop_words:
            if stem:
                tokens.append(stemmer.stem(token))
            else:
                tokens.append(token)
    return " ".join(tokens)



#aggregates the response from the sentiment algorithm and returns a result object with score, most pos index, and most neg index 
def aggregateData(data):
    # declaring and initializing return varaible 
    result = {'score': 0, 'posIndex': 0 , 'negIndex': 0, 'positive': 0 , 'negative': 0}

    pos = 0
    neg = 0
    numOfTweets = 0
    
    # loops through the results array in the json response
    for x in data['results']:   
        numOfTweets += 1            # counts the number of tweets
        if x['prediction'] == "POSITIVE":   
            pos +=1          # counts the number of tweets that have a positive prediction
        else: 
            neg += 1        # counts the number of tweets with a negativee prediction 
    score = (pos - neg) /numOfTweets     # calculates the score 

    # sets the score of the result
    result['score'] = score
    result['positive'] = pos
    result['negative'] = neg
    

    mostNeg = 0
    mostPos = 0
    index = 0

    for x in data['results']:
        if x['probability'] > mostPos:   # if the probability for positive is greater than the current mosPos 
            mostPos = x['probability']   # set mostPos to current probablity 
            mostPosIndex = index            # sets the index
        if x['probability'] < mostNeg:   # if the probability for negative is greater than the current mostNeg 
            mostNeg = x['probability']   # set mostNeg to current probability 
            mostNegIndex = index            # sets the index
        index += 1                      # increments the index 

    # sets the results posIndex and negIndex values 
    result['posIndex'] = mostPosIndex
    result['negIndex'] = mostNegIndex

    return result

def get_leaderboard():
    cluster = MongoClient(database_connect)
    db = cluster["DSS"]
    collection = db["Search_Records"]

   #queries most postive usernames for leaderboards
    mostPosUser = list(collection.find({"type":"user"}).sort("score", -1))
    uniqueMostPosUser = []
    temp = []

    for x in mostPosUser:
        if x['query'] not in temp:
            uniqueMostPosUser.append(x)
            temp.append(x['query'])
 
    #reverses list to get most negative usernames for leaderboards
    negUser = uniqueMostPosUser[::-1]
    
    #queries most positive hashtag for leaderboards
    mostPosHashtag = list(collection.find({"type":"hashtag"}).sort("score", -1))
    uniqueMostPosHashtag = []
    temp = []

    for x in mostPosHashtag:
        if x['query'] not in temp:
            uniqueMostPosHashtag.append(x)
            temp.append(x['query'])

    #reverses list to get most negative hashtag for leaderboards
    negHash = uniqueMostPosHashtag[::-1]

    #queries 10 most frequently searched hashtags 
    result = collection.aggregate([
        # Match the type to be user
        { "$match": { "type":"hashtag" } },

        # Group the documents with the same query and count them
        { "$group": {
            "_id": {
            "query": "$query"
            },
            "count": { "$sum": 1 }
        }},
        # sort the documents by most frequent
        { "$sort": {
            "count": -1
            }
        },{ "$limit" : 10 }
        ])
    mostFrequentHash = []
    for x in result:
        mostFrequentHash.append(list(collection.find({"query": x['_id']['query']}).sort("timeLog", -1).limit(1)))
   

    #queries 10 most frequently searched usernames
    result = collection.aggregate([
        # Match the type to be user
        { "$match": { "type":"user" } },

        # Group the documents with the same query and count them
        { "$group": {
            "_id": {
            "query": "$query"
            },
            "count": { "$sum": 1 }
        }},
        # sort the documents by most frequent
        { "$sort": {
            "count": -1
            }
        },{ "$limit" : 10 }
        ])
    mostFrequentUser = []
    for x in result:
        mostFrequentUser.append(list(collection.find({"query": x['_id']['query']}).sort("timeLog", -1).limit(1)))


    now = datetime.now()
    # schema for leaderboard creation
    post = {
         "postiveUser" : uniqueMostPosUser[:10],
         "negativeUser" : negUser[:10],
         "frequencyUser" : list(mostFrequentUser),
         "postiveHash" : uniqueMostPosHashtag[:10],
         "negativeHash" : negHash[:10],
         "frequencyHash" : list(mostFrequentHash),
         "timeCreated" : now     
    }
    LBcollection = db["Leaderboard_Cache"]  
    LBcollection.insert_one(post)
    return post