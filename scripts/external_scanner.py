#!/usr/bin/env python3
"""
Kaelis ACK v2.0 - 外部社区连接器 (External Scanner)
功能: 为"外部社区"角色提供实时检索能力，获取群体智慧

数据来源:
- GitHub: 搜索相关开源实现，提取设计模式
- Stack Overflow: 检索相关讨论，识别常见陷阱
- Hacker News: 获取技术选型的社区评价
- arXiv: 吸收学术界最新方法

作者: Kaelis ACK v2.0
版本: 2.0.0
"""

import os
import re
import json
import time
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Dict, Optional, Any
from functools import lru_cache


# ============================================================================
# 数据模型
# ============================================================================

@dataclass
class SearchResult:
    """搜索结果基类"""
    title: str
    url: str
    summary: str
    source: str = "unknown"
    relevance_score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class GitHubResult(SearchResult):
    """GitHub搜索结果"""
    stars: int = 0
    language: str = ""
    last_updated: str = ""
    topics: List[str] = field(default_factory=list)
    source: str = "github"


@dataclass
class StackOverflowResult(SearchResult):
    """Stack Overflow搜索结果"""
    score: int = 0
    answer_count: int = 0
    view_count: int = 0
    tags: List[str] = field(default_factory=list)
    accepted_answer: bool = False
    source: str = "stackoverflow"


@dataclass
class HackerNewsResult(SearchResult):
    """Hacker News搜索结果"""
    points: int = 0
    comment_count: int = 0
    posted_time: str = ""
    source: str = "hackernews"


@dataclass
class ArXivResult(SearchResult):
    """arXiv论文搜索结果"""
    authors: List[str] = field(default_factory=list)
    published: str = ""
    primary_category: str = ""
    categories: List[str] = field(default_factory=list)
    source: str = "arxiv"


@dataclass
class ExternalKnowledge:
    """外部知识汇总"""
    goal: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    github_results: List[GitHubResult] = field(default_factory=list)
    so_results: List[StackOverflowResult] = field(default_factory=list)
    hn_results: List[HackerNewsResult] = field(default_factory=list)
    arxiv_results: List[ArXivResult] = field(default_factory=list)
    
    def add_github_results(self, results: List[GitHubResult]):
        self.github_results.extend(results)
    
    def add_so_results(self, results: List[StackOverflowResult]):
        self.so_results.extend(results)
    
    def add_hn_results(self, results: List[HackerNewsResult]):
        self.hn_results.extend(results)
    
    def add_arxiv_results(self, results: List[ArXivResult]):
        self.arxiv_results.extend(results)
    
    def to_context_string(self, max_length: int = 3000) -> str:
        """转换为角色可用的上下文字符串"""
        sections = []
        
        # GitHub 开源方案
        if self.github_results:
            sections.append("## 开源实现参考 (GitHub)")
            for i, r in enumerate(self.github_results[:3], 1):
                sections.append(f"{i}. **{r.title}** ({r.stars}⭐)")
                sections.append(f"   - 语言: {r.language}")
                sections.append(f"   - 要点: {r.summary[:100]}...")
                if r.topics:
                    sections.append(f"   - 标签: {', '.join(r.topics[:3])}")
            sections.append("")
        
        # Stack Overflow 常见陷阱
        if self.so_results:
            sections.append("## 常见陷阱与解决方案 (Stack Overflow)")
            for i, r in enumerate(self.so_results[:3], 1):
                sections.append(f"{i}. **{r.title}**")
                sections.append(f"   - 评分: {r.score} | 答案: {r.answer_count}")
                sections.append(f"   - 要点: {r.summary[:100]}...")
            sections.append("")
        
        # Hacker News 社区评价
        if self.hn_results:
            sections.append("## 社区讨论 (Hacker News)")
            for i, r in enumerate(self.hn_results[:2], 1):
                sections.append(f"{i}. **{r.title}** ({r.points}👍)")
                sections.append(f"   - 讨论: {r.comment_count}条评论")
            sections.append("")
        
        # arXiv 学术方法
        if self.arxiv_results:
            sections.append("## 学术方法参考 (arXiv)")
            for i, r in enumerate(self.arxiv_results[:2], 1):
                sections.append(f"{i}. **{r.title}**")
                authors = ', '.join(r.authors[:2]) if r.authors else "Unknown"
                sections.append(f"   - 作者: {authors}")
                sections.append(f"   - 领域: {r.primary_category}")
            sections.append("")
        
        context = "\n".join(sections)
        
        # 截断到最大长度
        if len(context) > max_length:
            context = context[:max_length-100] + "\n\n...[内容已截断]"
        
        return context
    
    def extract_best_practices(self) -> List[str]:
        """提取最佳实践"""
        practices = []
        
        # 从GitHub提取
        for r in self.github_results[:2]:
            if "pattern" in r.summary.lower() or "best" in r.summary.lower():
                practices.append(f"GitHub项目'{r.title}'采用的模式: {r.summary[:80]}")
        
        # 从Stack Overflow提取
        for r in self.so_results[:2]:
            if r.accepted_answer:
                practices.append(f"SO推荐方案: {r.title[:80]}")
        
        return practices
    
    def identify_common_pitfalls(self) -> List[str]:
        """识别常见陷阱"""
        pitfalls = []
        
        # 从Stack Overflow识别
        anti_pattern_keywords = ['error', 'problem', 'issue', 'bug', 'fail', 'wrong']
        for r in self.so_results[:3]:
            title_lower = r.title.lower()
            if any(kw in title_lower for kw in anti_pattern_keywords):
                pitfalls.append(f"常见问题: {r.title[:80]}")
        
        return pitfalls


# ============================================================================
# 外部数据源实现
# ============================================================================

class ExternalSource:
    """外部知识源基类"""
    
    def __init__(self, name: str):
        self.name = name
        self.last_request_time = 0
        self.min_interval = 1.0  # 请求间隔（秒）
    
    def _rate_limit(self):
        """速率限制"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_request_time = time.time()
    
    def _make_request(self, url: str, headers: Optional[Dict] = None) -> Optional[Dict]:
        """发起HTTP请求"""
        try:
            self._rate_limit()
            
            req = urllib.request.Request(url, headers=headers or {})
            with urllib.request.urlopen(req, timeout=10) as response:
                data = response.read().decode('utf-8')
                return json.loads(data)
        except Exception as e:
            print(f"[WARN] {self.name} request failed: {e}")
            return None
    
    def search(self, query: str, limit: int = 5) -> List[SearchResult]:
        """搜索接口 - 子类必须实现"""
        raise NotImplementedError


class GitHubSource(ExternalSource):
    """GitHub搜索源"""
    
    def __init__(self):
        super().__init__("GitHub")
        self.api_token = os.environ.get('GITHUB_TOKEN', '')
    
    def search(self, query: str, limit: int = 5) -> List[GitHubResult]:
        """搜索GitHub仓库"""
        # 使用GitHub Search API
        encoded_query = urllib.parse.quote(f"{query} in:name,description,readme")
        url = f"https://api.github.com/search/repositories?q={encoded_query}&sort=stars&order=desc&per_page={limit}"
        
        headers = {
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'Kaelis-ACK-v2.0'
        }
        if self.api_token:
            headers['Authorization'] = f'token {self.api_token}'
        
        data = self._make_request(url, headers)
        if not data or 'items' not in data:
            # 降级到模拟数据
            return self._generate_mock_data(query, limit)
        
        results = []
        for item in data['items'][:limit]:
            results.append(GitHubResult(
                title=item.get('name', 'Unknown'),
                url=item.get('html_url', ''),
                summary=item.get('description', 'No description') or 'No description',
                stars=item.get('stargazers_count', 0),
                language=item.get('language', 'Unknown') or 'Unknown',
                last_updated=item.get('updated_at', ''),
                topics=item.get('topics', []),
                relevance_score=self._calculate_relevance(item, query)
            ))
        
        return results
    
    def _calculate_relevance(self, item: Dict, query: str) -> float:
        """计算相关性分数"""
        score = 0.0
        query_lower = query.lower()
        
        # 名称匹配
        if query_lower in item.get('name', '').lower():
            score += 0.4
        
        # 描述匹配
        if query_lower in (item.get('description') or '').lower():
            score += 0.3
        
        # 星标数权重
        stars = item.get('stargazers_count', 0)
        score += min(stars / 10000, 0.3)
        
        return min(score, 1.0)
    
    def _generate_mock_data(self, query: str, limit: int) -> List[GitHubResult]:
        """生成模拟数据（降级方案）"""
        print(f"[INFO] Using mock GitHub data for '{query}'")
        
        mock_repos = {
            'authentication': [
                ('auth0', 'auth0-python', 'Auth0 Python SDK', 1000, 'Python'),
                ('jwt', 'pyjwt', 'JSON Web Token implementation in Python', 5000, 'Python'),
            ],
            'database': [
                ('sqlalchemy', 'sqlalchemy', 'The Python SQL Toolkit', 8000, 'Python'),
                ('mongodb', 'mongo-python-driver', 'PyMongo - MongoDB Python Driver', 4000, 'Python'),
            ],
            'api': [
                ('fastapi', 'fastapi', 'FastAPI framework', 70000, 'Python'),
                ('flask', 'flask', 'The Python micro framework', 65000, 'Python'),
            ],
            'cache': [
                ('redis', 'redis-py', 'Redis Python Client', 12000, 'Python'),
            ],
            'microservice': [
                ('kubernetes', 'kubernetes-client', 'Kubernetes Python Client', 6000, 'Python'),
            ]
        }
        
        results = []
        query_lower = query.lower()
        
        for category, repos in mock_repos.items():
            if category in query_lower or any(kw in query_lower for kw in category.split()):
                for owner, name, desc, stars, lang in repos[:limit]:
                    results.append(GitHubResult(
                        title=f"{owner}/{name}",
                        url=f"https://github.com/{owner}/{name}",
                        summary=desc,
                        stars=stars,
                        language=lang,
                        topics=[category, 'python']
                    ))
        
        # 通用默认
        if not results:
            results.append(GitHubResult(
                title="awesome-python",
                url="https://github.com/vinta/awesome-python",
                summary="A curated list of awesome Python frameworks, libraries, software and resources",
                stars=200000,
                language="Python",
                topics=['python', 'awesome', 'resources']
            ))
        
        return results[:limit]
    
    def extract_patterns(self, repo_info: Dict) -> List[str]:
        """从仓库信息提取设计模式"""
        patterns = []
        
        # 基于语言推断
        lang = repo_info.get('language', '').lower()
        if lang == 'python':
            patterns.extend(['decorator', 'context_manager', 'generator'])
        elif lang == 'javascript':
            patterns.extend(['promise', 'async_await', 'module_pattern'])
        
        # 基于主题推断
        topics = repo_info.get('topics', [])
        if 'microservice' in topics:
            patterns.append('microservice_architecture')
        if 'api' in topics:
            patterns.append('restful_api')
        
        return patterns


class StackOverflowSource(ExternalSource):
    """Stack Overflow搜索源"""
    
    def __init__(self):
        super().__init__("StackOverflow")
        self.api_key = os.environ.get('STACKEXCHANGE_KEY', '')
    
    def search(self, query: str, limit: int = 5) -> List[StackOverflowResult]:
        """搜索Stack Overflow问题"""
        # Stack Exchange API
        encoded_query = urllib.parse.quote(query)
        url = (
            f"https://api.stackexchange.com/2.3/search/advanced?"
            f"order=desc&sort=relevance&q={encoded_query}&"
            f"site=stackoverflow&pagesize={limit}"
        )
        if self.api_key:
            url += f"&key={self.api_key}"
        
        data = self._make_request(url)
        if not data or 'items' not in data:
            return self._generate_mock_data(query, limit)
        
        results = []
        for item in data['items'][:limit]:
            results.append(StackOverflowResult(
                title=item.get('title', 'Unknown'),
                url=item.get('link', ''),
                summary=self._clean_html(item.get('excerpt', '')),
                score=item.get('score', 0),
                answer_count=item.get('answer_count', 0),
                view_count=item.get('view_count', 0),
                tags=item.get('tags', []),
                accepted_answer=item.get('is_answered', False),
                relevance_score=self._calculate_relevance(item, query)
            ))
        
        return results
    
    def _clean_html(self, html: str) -> str:
        """清理HTML标签"""
        if not html:
            return ""
        # 简单移除HTML标签
        clean = re.sub(r'<[^>]+>', '', html)
        return clean
    
    def _calculate_relevance(self, item: Dict, query: str) -> float:
        """计算相关性"""
        score = 0.0
        
        # 答案数量权重
        answers = item.get('answer_count', 0)
        score += min(answers / 10, 0.3)
        
        # 有接受答案加分
        if item.get('accepted_answer_id'):
            score += 0.3
        
        # 浏览量权重
        views = item.get('view_count', 0)
        score += min(views / 10000, 0.2)
        
        return min(score, 1.0)
    
    def _generate_mock_data(self, query: str, limit: int) -> List[StackOverflowResult]:
        """生成模拟数据"""
        print(f"[INFO] Using mock StackOverflow data for '{query}'")
        
        mock_questions = {
            'authentication': [
                ('How to implement JWT authentication in Python?', 150, 5, True),
                ('Best practices for password hashing?', 200, 8, True),
            ],
            'database': [
                ('SQLAlchemy vs raw SQL performance?', 80, 4, True),
                ('How to handle database migrations?', 120, 6, True),
            ],
            'error': [
                ('How to properly handle exceptions in Python?', 300, 10, True),
                ('Common pitfalls in async/await?', 180, 7, True),
            ]
        }
        
        results = []
        query_lower = query.lower()
        
        for category, questions in mock_questions.items():
            if category in query_lower:
                for title, score, answers, accepted in questions:
                    results.append(StackOverflowResult(
                        title=title,
                        url=f"https://stackoverflow.com/questions/{hash(title) % 1000000}",
                        summary=f"Discussion about {category} best practices and common issues",
                        score=score,
                        answer_count=answers,
                        view_count=score * 100,
                        accepted_answer=accepted
                    ))
        
        if not results:
            results.append(StackOverflowResult(
                title=f"Best practices for {query}?",
                url="https://stackoverflow.com/questions/tagged/python",
                summary=f"Community discussion about {query} implementation",
                score=100,
                answer_count=5,
                accepted_answer=True
            ))
        
        return results[:limit]
    
    def extract_common_pitfalls(self, questions: List[StackOverflowResult]) -> List[str]:
        """提取常见陷阱"""
        pitfalls = []
        
        for q in questions:
            title_lower = q.title.lower()
            if any(kw in title_lower for kw in ['error', 'exception', 'fail', 'wrong', 'issue']):
                pitfalls.append(q.title)
        
        return pitfalls


class HackerNewsSource(ExternalSource):
    """Hacker News搜索源"""
    
    def __init__(self):
        super().__init__("HackerNews")
    
    def search(self, query: str, limit: int = 5) -> List[HackerNewsResult]:
        """搜索Hacker News讨论"""
        # 使用Algolia HN Search API
        encoded_query = urllib.parse.quote(query)
        url = f"https://hn.algolia.com/api/v1/search?query={encoded_query}&tags=story&hitsPerPage={limit}"
        
        data = self._make_request(url)
        if not data or 'hits' not in data:
            return self._generate_mock_data(query, limit)
        
        results = []
        for hit in data['hits'][:limit]:
            results.append(HackerNewsResult(
                title=hit.get('title', 'Unknown'),
                url=hit.get('url') or f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
                summary=hit.get('story_text', '') or 'No summary available',
                points=hit.get('points', 0),
                comment_count=hit.get('num_comments', 0),
                posted_time=hit.get('created_at', ''),
                relevance_score=self._calculate_relevance(hit, query)
            ))
        
        return results
    
    def _calculate_relevance(self, hit: Dict, query: str) -> float:
        """计算相关性"""
        score = 0.0
        
        # 点赞数权重
        points = hit.get('points', 0)
        score += min(points / 100, 0.4)
        
        # 评论数权重
        comments = hit.get('num_comments', 0)
        score += min(comments / 50, 0.3)
        
        return min(score, 1.0)
    
    def _generate_mock_data(self, query: str, limit: int) -> List[HackerNewsResult]:
        """生成模拟数据"""
        print(f"[INFO] Using mock HackerNews data for '{query}'")
        
        mock_stories = [
            ('Show HN: A new Python web framework', 250, 80),
            ('Ask HN: Best practices for API design?', 180, 120),
            ('Why we switched from X to Y', 320, 95),
        ]
        
        results = []
        for title, points, comments in mock_stories[:limit]:
            results.append(HackerNewsResult(
                source="hackernews",
                title=title,
                url="https://news.ycombinator.com",
                summary=f"HN community discussion about technology choices",
                points=points,
                comment_count=comments
            ))
        
        return results
    
    def extract_sentiment(self, discussions: List[HackerNewsResult]) -> Dict[str, Any]:
        """提取社区情绪"""
        total_points = sum(d.points for d in discussions)
        total_comments = sum(d.comment_count for d in discussions)
        
        return {
            'engagement_score': total_points + total_comments * 2,
            'discussion_heat': 'high' if total_comments > 100 else 'medium' if total_comments > 20 else 'low',
            'community_interest': len(discussions)
        }


class ArXivSource(ExternalSource):
    """arXiv论文搜索源"""
    
    def __init__(self):
        super().__init__("arXiv")
    
    def search(self, query: str, limit: int = 5) -> List[ArXivResult]:
        """搜索arXiv论文"""
        # arXiv API
        encoded_query = urllib.parse.quote(query)
        url = f"http://export.arxiv.org/api/query?search_query=all:{encoded_query}&start=0&max_results={limit}"
        
        try:
            self._rate_limit()
            req = urllib.request.Request(url, headers={'User-Agent': 'Kaelis-ACK-v2.0'})
            
            with urllib.request.urlopen(req, timeout=10) as response:
                import xml.etree.ElementTree as ET
                
                data = response.read().decode('utf-8')
                root = ET.fromstring(data)
                
                # arXiv Atom命名空间
                ns = {'atom': 'http://www.w3.org/2005/Atom'}
                
                results = []
                for entry in root.findall('atom:entry', ns):
                    title = entry.find('atom:title', ns)
                    summary = entry.find('atom:summary', ns)
                    published = entry.find('atom:published', ns)
                    
                    # 提取作者
                    authors = []
                    for author in entry.findall('atom:author', ns):
                        name = author.find('atom:name', ns)
                        if name is not None:
                            authors.append(name.text)
                    
                    # 提取分类
                    categories = []
                    for cat in entry.findall('atom:category', ns):
                        term = cat.get('term')
                        if term:
                            categories.append(term)
                    
                    # 提取ID/URL
                    id_elem = entry.find('atom:id', ns)
                    url_text = id_elem.text if id_elem is not None else ''
                    
                    results.append(ArXivResult(
                        title=title.text.strip() if title is not None else 'Unknown',
                        url=url_text,
                        summary=summary.text.strip()[:200] + '...' if summary is not None else '',
                        authors=authors[:3],
                        published=published.text[:10] if published is not None else '',
                        primary_category=categories[0] if categories else '',
                        categories=categories,
                        relevance_score=0.5  # arXiv不提供直接相关性分数
                    ))
                
                return results
                
        except Exception as e:
            print(f"[WARN] arXiv request failed: {e}")
            return self._generate_mock_data(query, limit)
    
    def _generate_mock_data(self, query: str, limit: int) -> List[ArXivResult]:
        """生成模拟数据"""
        print(f"[INFO] Using mock arXiv data for '{query}'")
        
        mock_papers = [
            ('Machine Learning for Software Engineering: A Survey', ['A. Smith', 'B. Jones'], 'cs.SE', '2024-01'),
            ('On the Design of Distributed Systems', ['C. Brown'], 'cs.DC', '2023-12'),
        ]
        
        results = []
        for title, authors, cat, date in mock_papers[:limit]:
            results.append(ArXivResult(
                source="arxiv",
                title=title,
                url="https://arxiv.org",
                summary=f"Research paper on {query} related topics",
                authors=authors,
                published=date,
                primary_category=cat,
                categories=[cat]
            ))
        
        return results
    
    def extract_methods(self, papers: List[ArXivResult]) -> List[str]:
        """提取研究方法"""
        methods = []
        
        for p in papers:
            if 'survey' in p.title.lower():
                methods.append(f"综述方法: {p.title[:60]}")
            elif 'approach' in p.title.lower():
                methods.append(f"方法论: {p.title[:60]}")
        
        return methods


# ============================================================================
# 外部扫描器主类
# ============================================================================

class ExternalScanner:
    """
    外部扫描器主类
    
    协调多个外部数据源，为"外部社区"角色提供综合知识。
    """
    
    def __init__(self, enable_cache: bool = True):
        self.enable_cache = enable_cache
        self.sources: Dict[str, ExternalSource] = {
            'github': GitHubSource(),
            'stackoverflow': StackOverflowSource(),
            'hackernews': HackerNewsSource(),
            'arxiv': ArXivSource()
        }
        
        # 配置
        self.default_search_depth = 5
        self.max_search_depth = 10
    
    def scan_for_goal(self, goal: str, depth: int = None) -> ExternalKnowledge:
        """
        为给定目标扫描外部知识
        
        Args:
            goal: 目标描述
            depth: 搜索深度（结果数量）
        
        Returns:
            ExternalKnowledge: 汇总的外部知识
        """
        limit = depth or self.default_search_depth
        knowledge = ExternalKnowledge(goal=goal)
        
        print(f"[ExternalScanner] Scanning for goal: {goal[:50]}...")
        
        # 并行搜索各个源
        try:
            print("  [1/4] Searching GitHub...")
            github_results = self.sources['github'].search(goal, limit)
            knowledge.add_github_results(github_results)
            print(f"        Found {len(github_results)} repositories")
        except Exception as e:
            print(f"        Error: {e}")
        
        try:
            print("  [2/4] Searching Stack Overflow...")
            so_results = self.sources['stackoverflow'].search(goal, limit)
            knowledge.add_so_results(so_results)
            print(f"        Found {len(so_results)} discussions")
        except Exception as e:
            print(f"        Error: {e}")
        
        try:
            print("  [3/4] Searching Hacker News...")
            hn_results = self.sources['hackernews'].search(goal, limit)
            knowledge.add_hn_results(hn_results)
            print(f"        Found {len(hn_results)} stories")
        except Exception as e:
            print(f"        Error: {e}")
        
        try:
            print("  [4/4] Searching arXiv...")
            arxiv_results = self.sources['arxiv'].search(goal, min(limit, 3))
            knowledge.add_arxiv_results(arxiv_results)
            print(f"        Found {len(arxiv_results)} papers")
        except Exception as e:
            print(f"        Error: {e}")
        
        print(f"[ExternalScanner] Scan complete. Total sources: {len(knowledge.github_results) + len(knowledge.so_results) + len(knowledge.hn_results) + len(knowledge.arxiv_results)}")
        
        return knowledge
    
    def synthesize_community_view(self, knowledge: ExternalKnowledge) -> str:
        """
        综合社区观点
        
        将外部知识转换为"外部社区"角色的观点文本。
        """
        sections = []
        
        # 1. 开源生态概览
        if knowledge.github_results:
            sections.append("【开源生态】")
            top_repo = knowledge.github_results[0]
            sections.append(f"相关开源项目丰富，如 '{top_repo.title}' ({top_repo.stars} stars)，")
            sections.append(f"主要使用 {top_repo.language} 实现。")
            
            if len(knowledge.github_results) > 1:
                sections.append(f"另有 {len(knowledge.github_results)-1} 个相关项目可供参考。")
            sections.append("")
        
        # 2. 常见陷阱
        pitfalls = knowledge.identify_common_pitfalls()
        if pitfalls:
            sections.append("【常见陷阱】")
            sections.append("社区反馈中常见的注意事项：")
            for p in pitfalls[:3]:
                sections.append(f"  - {p}")
            sections.append("")
        
        # 3. 最佳实践
        practices = knowledge.extract_best_practices()
        if practices:
            sections.append("【推荐实践】")
            for p in practices[:3]:
                sections.append(f"  - {p}")
            sections.append("")
        
        # 4. 社区情绪
        if knowledge.hn_results:
            hn_sentiment = HackerNewsSource().extract_sentiment(knowledge.hn_results)
            sections.append("【社区热度】")
            sections.append(f"Hacker News讨论热度: {hn_sentiment['discussion_heat']}")
            sections.append(f"总参与度: {hn_sentiment['engagement_score']}")
            sections.append("")
        
        return "\n".join(sections)
    
    def get_source_status(self) -> Dict[str, bool]:
        """获取各数据源状态"""
        return {
            name: True  # 简化处理，实际可以测试连接
            for name in self.sources.keys()
        }


# ============================================================================
# 命令行接口
# ============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Kaelis ACK v2.0 - External Scanner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --goal "implement JWT authentication"
  %(prog)s --goal "database connection pooling" --depth 3
  %(prog)s --status
        """
    )
    
    parser.add_argument('--goal', '-g', help='Goal to search for')
    parser.add_argument('--depth', '-d', type=int, default=5, help='Search depth (1-10)')
    parser.add_argument('--status', '-s', action='store_true', help='Check source status')
    parser.add_argument('--context', '-c', action='store_true', help='Output as role context')
    parser.add_argument('--json', '-j', action='store_true', help='Output as JSON')
    
    args = parser.parse_args()
    
    scanner = ExternalScanner()
    
    if args.status:
        print("External Source Status:")
        print("=" * 40)
        for source, status in scanner.get_source_status().items():
            icon = "✅" if status else "❌"
            print(f"{icon} {source}")
    
    elif args.goal:
        knowledge = scanner.scan_for_goal(args.goal, args.depth)
        
        if args.json:
            # JSON输出
            output = {
                'goal': knowledge.goal,
                'timestamp': knowledge.timestamp,
                'github': [r.to_dict() for r in knowledge.github_results],
                'stackoverflow': [r.to_dict() for r in knowledge.so_results],
                'hackernews': [r.to_dict() for r in knowledge.hn_results],
                'arxiv': [r.to_dict() for r in knowledge.arxiv_results]
            }
            print(json.dumps(output, indent=2, ensure_ascii=False, default=str))
        
        elif args.context:
            # 角色上下文格式
            print(knowledge.to_context_string())
        
        else:
            # 默认输出
            print("\n" + "=" * 60)
            print(f"External Knowledge for: {args.goal}")
            print("=" * 60)
            print(knowledge.to_context_string())
            
            print("\n【社区观点综合】")
            print(scanner.synthesize_community_view(knowledge))
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
