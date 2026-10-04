"""
Movie Search Handler for MASTER-MUSIC-BOT
Integrates the movie-downloader API to search and retrieve movies
"""

import aiohttp
import asyncio
from typing import Optional, List, Dict
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from core.decorators import handle_error, language


class MovieAPI:
    """Handler for movie-downloader API interactions"""
    
    BASE_URL = "https://movie-downloader-api.vercel.app/api"
    
    @staticmethod
    async def search(query: str) -> Optional[List[Dict]]:
        """
        Search movies via the API
        
        Args:
            query: Movie title to search for
            
        Returns:
            List of movie results or None if error
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{MovieAPI.BASE_URL}/search",
                    params={"q": query},
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("results", []) if isinstance(data, dict) else data
                    return None
        except asyncio.TimeoutError:
            return None
        except Exception as e:
            print(f"Movie API error: {e}")
            return None


async def search_movie(query: str) -> Optional[str]:
    """
    Search for a movie and return formatted result
    
    Args:
        query: Movie search query
        
    Returns:
        Formatted movie info string or None
    """
    if not query or query.strip() == "":
        return None
    
    results = await MovieAPI.search(query.strip())
    
    if not results or len(results) == 0:
        return None
    
    # Format first 5 results
    formatted = "🎬 **Movie Search Results:**\n\n"
    
    for i, movie in enumerate(results[:5], 1):
        title = movie.get("title", "N/A")
        year = movie.get("year", "")
        imdb_id = movie.get("imdbID", "")
        poster = movie.get("poster", "")
        
        year_str = f" ({year})" if year else ""
        imdb_link = f"[IMDb](https://imdb.com/title/{imdb_id})" if imdb_id else "No link"
        
        formatted += f"{i}. **{title}**{year_str}\n"
        formatted += f"   {imdb_link}\n\n"
    
    return formatted


def create_movie_keyboard(results: List[Dict]) -> InlineKeyboardMarkup:
    """
    Create inline keyboard with movie options
    
    Args:
        results: List of movie results from API
        
    Returns:
        InlineKeyboardMarkup with movie buttons
    """
    buttons = []
    
    for movie in results[:5]:
        title = movie.get("title", "Unknown")[:20]
        imdb_id = movie.get("imdbID", "")
        
        if imdb_id:
            buttons.append([
                InlineKeyboardButton(
                    text=f"🎬 {title}",
                    url=f"https://imdb.com/title/{imdb_id}"
                )
            ])
    
    if buttons:
        buttons.append([
            InlineKeyboardButton(text="❌ Close", callback_data="close_movie")
        ])
    
    return InlineKeyboardMarkup(buttons) if buttons else None
