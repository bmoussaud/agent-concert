#!/bin/bash
SPOTIFY_API_KEY="BQC9IK6yT43zBi79mjk3PFi3zUVn9pYGs0l0VAHbz4-zEPPsOf8tGbzoRRkhNLEKo-tfOSDPgxEl9uCUB5ooefg_B9ApZFWshTIG8wMUR_KNc9k827xgortpEhRAbOSAjmg2n88ImLPTus7FXwkAMJIDKmqxx2y7rxMo2_VGLuOtAPHO8NueKC9T-98Owwltq2P6p90kUt55DoIxnErs0Tu_-VyQ-VLFRRfh4kLNLp2OqbeezXhR86CY45lL3pvB82o1k6F2rSPWEJ0kOSB4nHc9WiDN6TPS-X43wJYLM3rbRygElgDv8HlOfmn5lW1QF5DRP928uXGNcPxvOTiqpG67szds7Ik"
curl --request GET 'https://api.spotify.com/v1/me' --header "Authorization: Bearer ${SPOTIFY_API_KEY}"  | jq


#curl --request GET 'https://api.spotify.com/v1/me/playlists' --header "Authorization: Bearer ${SPOTIFY_API_KEY}"  | jq

curl "https://api.setlist.fm/rest/1.0/search/setlists?countryCode=GB&lastUpdated=20260430120000&year=2026&p=1&artistMbid=e212efdf-98b2-4dce-92ed-62cfc1e29854" --header "x-api-key: 2b3e4c8e-1c9d-4a7b-9c0f-1cbbd8a0b1e5" | jq
