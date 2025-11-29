from flask import Flask, request, jsonify
from pytubefix import YouTube
from pytubefix.innertube import InnerTube
import re
import os

app = Flask(__name__)

def get_yt_object(url, po_token=None, visitor_data=None):
    """
    Creates a YouTube object, trying with 'WEB' client first and falling back.
    Allows for manual po_token and visitor_data.
    """
    if po_token and visitor_data:
        try:
            # Use manual po_token and visitor_data
            innertube = InnerTube(client='WEB', use_po_token=True)
            innertube.context['client']['visitorData'] = visitor_data
            innertube.context['serviceIntegrityDimensions']['poToken'] = po_token
            yt = YouTube(url, innertube_client=innertube)
            _ = yt.title # check if it works
            return yt
        except Exception as e:
            print(f"Manual po_token failed: {e}")
            raise e

    try:
        # First attempt with 'WEB' client for PoToken generation
        yt = YouTube(url, 'WEB')
        # Perform a quick check to see if we get blocked
        _ = yt.title 
        return yt
    except Exception as e:
        # If we are detected as a bot, pytubefix might raise an exception containing "bot"
        if 'bot' in str(e).lower():
            print("Bot detection with 'WEB' client. Falling back to default client.")
            # Fallback to default client
            try:
                yt = YouTube(url)
                return yt
            except Exception as fallback_e:
                print(f"Fallback failed as well: {fallback_e}")
                raise fallback_e
        else:
            # Re-raise other exceptions
            raise e

def download_video(url, resolution, po_token=None, visitor_data=None):
    try:
        yt = get_yt_object(url, po_token, visitor_data)
        
        # Debug: Print all available streams
        print(f"Available progressive streams for {url}:")
        for stream in yt.streams.filter(progressive=True, file_extension='mp4'):
            print(f"  - {stream.resolution} - {stream.mime_type}")
        
        stream = yt.streams.filter(progressive=True, file_extension='mp4', resolution=resolution).first()
        if stream:
            out_dir = f"./downloads/{url.split('v=')[1].split('&')[0]}"
            import os
            os.makedirs(out_dir, exist_ok=True)
            stream.download(output_path=out_dir)
            return True, None
        else:
            print(f"\nTrying non-progressive streams:")
            for stream in yt.streams.filter(file_extension='mp4', res=resolution):
                print(f"  - {stream.resolution} - {stream.mime_type} - audio: {stream.includes_audio_track}")
            
            return False, "Video with the specified resolution not found."
    except Exception as e:
        return False, str(e)

def get_video_info(url, po_token=None, visitor_data=None):
    try:
        yt = get_yt_object(url, po_token, visitor_data)
        stream = yt.streams.first()
        video_info = {
            "title": yt.title,
            "author": yt.author,
            "length": yt.length,
            "views": yt.views,
            "description": yt.description,
            "publish_date": yt.publish_date,
        }
        return video_info, None
    except Exception as e:
        return None, str(e)

def is_valid_youtube_url(url):
    pattern = r"^(https?://)?(www\.)?youtube\.com/watch\?v=[\w-]+(&\S*)?$"
    return re.match(pattern, url) is not None

@app.route('/download/<resolution>', methods=['POST'])
def download_by_resolution(resolution):
    data = request.get_json()
    url = data.get('url')
    po_token = data.get('po_token')
    visitor_data = data.get('visitor_data')
    
    if not url:
        return jsonify({"error": "Missing 'url' parameter in the request body."}), 400

    if not is_valid_youtube_url(url):
        return jsonify({"error": "Invalid YouTube URL."}), 400
    
    success, error_message = download_video(url, resolution, po_token, visitor_data)
    
    if success:
        return jsonify({"message": f"Video with resolution {resolution} downloaded successfully."}), 200
    else:
        return jsonify({"error": error_message}), 500

@app.route('/video_info', methods=['POST'])
def video_info():
    data = request.get_json()
    url = data.get('url')
    po_token = data.get('po_token')
    visitor_data = data.get('visitor_data')
    
    if not url:
        return jsonify({"error": "Missing 'url' parameter in the request body."}), 400

    if not is_valid_youtube_url(url):
        return jsonify({"error": "Invalid YouTube URL."}), 400
    
    video_info, error_message = get_video_info(url, po_token, visitor_data)
    
    if video_info:
        return jsonify(video_info), 200
    else:
        return jsonify({"error": error_message}), 500


@app.route('/available_resolutions', methods=['POST'])
def available_resolutions():
    data = request.get_json()
    url = data.get('url')
    po_token = data.get('po_token')
    visitor_data = data.get('visitor_data')
    
    if not url:
        return jsonify({"error": "Missing 'url' parameter in the request body."}), 400

    if not is_valid_youtube_url(url):
        return jsonify({"error": "Invalid YouTube URL."}), 400
    
    try:
        yt = get_yt_object(url, po_token, visitor_data)
        progressive_resolutions = list(set([
            stream.resolution 
            for stream in yt.streams.filter(progressive=True, file_extension='mp4')
            if stream.resolution
        ]))
        all_resolutions = list(set([
            stream.resolution 
            for stream in yt.streams.filter(file_extension='mp4')
            if stream.resolution
        ]))
        return jsonify({
            "progressive": sorted(progressive_resolutions),
            "all": sorted(all_resolutions)
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
