"""
Manim Documentation HTML Parser for Vector Database Storage
Efficiently extracts and structures information from Manim documentation HTML files
and stores them in ChromaDB for retrieval.
"""

from bs4 import BeautifulSoup
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import re
import json
import os
from pathlib import Path
import chromadb
from chromadb.config import Settings
from tqdm import tqdm


@dataclass
class ManimDocEntry:
    """Structured representation of a Manim documentation entry"""
    
    # Core identification
    qualified_name: str
    class_name: str
    module_path: str
    
    # Documentation content
    description: str
    parameters: List[Dict[str, str]]
    return_type: Optional[str]
    
    # Code examples
    examples: List[Dict[str, str]]
    
    # Inheritance and relationships
    base_classes: List[str]
    methods: List[str]
    attributes: List[str]
    
    # Metadata
    doc_url: str
    category: str  # e.g., "animation", "mobject", "scene"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)
    
    def to_embedding_text(self) -> str:
        """
        Generate optimized text for embedding generation.
        Combines all relevant information in a searchable format.
        """
        parts = [
            f"Class: {self.qualified_name}",
            f"Category: {self.category}",
            f"Description: {self.description}",
        ]
        
        if self.base_classes:
            parts.append(f"Inherits from: {', '.join(self.base_classes)}")
        
        if self.parameters:
            param_strs = [f"{p['name']} ({p['type']})" for p in self.parameters]
            parts.append(f"Parameters: {', '.join(param_strs)}")
        
        if self.methods:
            parts.append(f"Methods: {', '.join(self.methods[:10])}")  # Limit for token efficiency
        
        if self.examples:
            parts.append(f"Has {len(self.examples)} code example(s)")
            # Include first example for context
            if self.examples:
                parts.append(f"Example code: {self.examples[0]['code'][:200]}")
        
        return "\n".join(parts)


class ManimHTMLParser:
    """Parser for Manim documentation HTML files"""
    
    def __init__(self):
        self.soup = None
        
    def parse_file(self, html_path: str) -> Optional[ManimDocEntry]:
        """Parse HTML file and return structured entry"""
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        return self.parse_html(html_content, html_path)
    
    def parse_html(self, html_content: str, source_url: str = "") -> Optional[ManimDocEntry]:
        """Parse HTML content and extract Manim documentation"""
        self.soup = BeautifulSoup(html_content, 'html.parser')
        
        # Extract qualified name
        qualified_name = self._extract_qualified_name()
        if not qualified_name:
            return None
        
        # Parse module path and class name
        parts = qualified_name.split('.')
        class_name = parts[-1]
        module_path = '.'.join(parts[:-1])
        
        # Determine category from module path
        category = self._extract_category(module_path)
        
        return ManimDocEntry(
            qualified_name=qualified_name,
            class_name=class_name,
            module_path=module_path,
            description=self._extract_description(),
            parameters=self._extract_parameters(),
            return_type=self._extract_return_type(),
            examples=self._extract_examples(),
            base_classes=self._extract_base_classes(),
            methods=self._extract_methods(),
            attributes=self._extract_attributes(),
            doc_url=source_url,
            category=category
        )
    
    def _extract_qualified_name(self) -> Optional[str]:
        """Extract the qualified name (e.g., manim.animation.transform.ApplyComplexFunction)"""
        # Look for the qualified name paragraph
        qualified_p = self.soup.find('p', string=re.compile(r'^Qualified name:'))
        if qualified_p:
            code = qualified_p.find('code')
            if code:
                return code.get_text().strip()
        
        # Fallback: extract from class signature
        sig = self.soup.find('dt', class_='sig')
        if sig:
            sig_name = sig.find('span', class_='sig-name')
            if sig_name:
                return sig_name.get_text().strip()
        
        return None
    
    def _extract_category(self, module_path: str) -> str:
        """Extract category from module path"""
        if 'animation' in module_path:
            return 'animation'
        elif 'mobject' in module_path:
            return 'mobject'
        elif 'scene' in module_path:
            return 'scene'
        elif 'camera' in module_path:
            return 'camera'
        elif 'utils' in module_path:
            return 'utility'
        return 'other'
    
    def _extract_description(self) -> str:
        """Extract class description"""
        # Look for description in dd tag following the class signature
        dd = self.soup.find('dd')
        if dd:
            # Get first paragraph or text before methods/attributes sections
            description_parts = []
            for elem in dd.children:
                if elem.name == 'p' and elem.get('class') != ['rubric']:
                    description_parts.append(elem.get_text().strip())
                elif elem.name == 'p' and 'rubric' in elem.get('class', []):
                    break  # Stop at Methods/Attributes sections
            
            return ' '.join(description_parts).strip()
        
        return ""
    
    def _extract_parameters(self) -> List[Dict[str, str]]:
        """Extract function/method parameters"""
        parameters = []
        
        # Find parameter list in field-list
        field_list = self.soup.find('dl', class_='field-list')
        if field_list:
            params_field = field_list.find('dt', string=re.compile(r'Parameters'))
            if params_field:
                params_dd = params_field.find_next_sibling('dd')
                if params_dd:
                    # Extract each parameter
                    param_items = params_dd.find_all('li')
                    for item in param_items:
                        strong = item.find('strong')
                        if strong:
                            param_name = strong.get_text().strip()
                            
                            # Extract type information
                            param_type = ""
                            em = item.find('em')
                            if em:
                                param_type = em.get_text().strip()
                            
                            parameters.append({
                                'name': param_name,
                                'type': param_type,
                                'description': item.get_text().strip()
                            })
        
        return parameters
    
    def _extract_return_type(self) -> Optional[str]:
        """Extract return type if specified"""
        field_list = self.soup.find('dl', class_='field-list')
        if field_list:
            return_field = field_list.find('dt', string=re.compile(r'Return type'))
            if return_field:
                return_dd = return_field.find_next_sibling('dd')
                if return_dd:
                    return return_dd.get_text().strip()
        return None
    
    def _extract_examples(self) -> List[Dict[str, str]]:
        """Extract code examples with metadata"""
        examples = []
        
        # Find all code blocks with manim-binder attribute
        code_blocks = self.soup.find_all('pre', {'data-manim-binder': True})
        
        for i, block in enumerate(code_blocks):
            class_name = block.get('data-manim-classname', f'Example{i+1}')
            code = block.get_text().strip()
            
            examples.append({
                'name': class_name,
                'code': code,
                'language': 'python',
                'runnable': True
            })
        
        # Also look for regular code blocks
        if not examples:
            code_blocks = self.soup.find_all('pre')
            for i, block in enumerate(code_blocks):
                code = block.get_text().strip()
                if 'class' in code and 'Scene' in code:
                    examples.append({
                        'name': f'Example{i+1}',
                        'code': code,
                        'language': 'python',
                        'runnable': False
                    })
        
        return examples
    
    def _extract_base_classes(self) -> List[str]:
        """Extract base classes from signature"""
        bases = []
        
        # Look in class definition
        sig = self.soup.find('dt', class_='sig')
        if sig:
            # Find "Bases:" text
            dd = sig.find_next_sibling('dd')
            if dd:
                bases_p = dd.find('p', string=re.compile(r'^Bases:'))
                if bases_p:
                    # Extract class links
                    links = bases_p.find_all('a', class_='reference')
                    for link in links:
                        bases.append(link.get_text().strip())
        
        return bases
    
    def _extract_methods(self) -> List[str]:
        """Extract method names"""
        methods = []
        
        # Find Methods section in autosummary table
        tables = self.soup.find_all('table', class_='autosummary')
        for table in tables:
            # Check if this is methods table (look for preceding rubric)
            prev_rubric = table.find_previous('p', class_='rubric')
            if prev_rubric and 'Methods' in prev_rubric.get_text():
                rows = table.find_all('tr')
                for row in rows:
                    code = row.find('code')
                    if code:
                        method_name = code.get_text().strip()
                        methods.append(method_name)
        
        return methods
    
    def _extract_attributes(self) -> List[str]:
        """Extract attribute names"""
        attributes = []
        
        # Find Attributes section in autosummary table
        tables = self.soup.find_all('table', class_='autosummary')
        for table in tables:
            prev_rubric = table.find_previous('p', class_='rubric')
            if prev_rubric and 'Attributes' in prev_rubric.get_text():
                rows = table.find_all('tr')
                for row in rows:
                    code = row.find('code')
                    if code:
                        attr_name = code.get_text().strip()
                        attributes.append(attr_name)
        
        return attributes


class ManimDocVectorizer:
    """
    Prepares parsed documentation for vector database insertion.
    Generates multiple embeddings per entry for better retrieval.
    """
    
    @staticmethod
    def create_chunks(entry: ManimDocEntry) -> List[Dict[str, Any]]:
        """
        Create multiple searchable chunks from a single entry.
        This improves retrieval accuracy by creating specialized views.
        """
        chunks = []
        
        # Chunk 1: Main class overview
        chunks.append({
            'id': f"{entry.qualified_name}:overview",
            'text': entry.to_embedding_text(),
            'metadata': {
                'type': 'overview',
                'class_name': entry.class_name,
                'qualified_name': entry.qualified_name,
                'category': entry.category,
                'url': entry.doc_url
            }
        })
        
        # Chunk 2: Each example as separate chunk
        for i, example in enumerate(entry.examples):
            chunks.append({
                'id': f"{entry.qualified_name}:example:{i}",
                'text': f"Class: {entry.qualified_name}\nExample: {example['name']}\n\n{example['code']}",
                'metadata': {
                    'type': 'example',
                    'class_name': entry.class_name,
                    'qualified_name': entry.qualified_name,
                    'category': entry.category,
                    'example_name': example['name'],
                    'url': entry.doc_url
                }
            })
        
        # Chunk 3: Parameter-focused (for parameter searches)
        if entry.parameters:
            param_text = f"Class: {entry.qualified_name}\nParameters:\n"
            for param in entry.parameters:
                param_text += f"- {param['name']} ({param['type']}): {param['description']}\n"
            
            chunks.append({
                'id': f"{entry.qualified_name}:parameters",
                'text': param_text,
                'metadata': {
                    'type': 'parameters',
                    'class_name': entry.class_name,
                    'qualified_name': entry.qualified_name,
                    'category': entry.category,
                    'url': entry.doc_url
                }
            })
        
        return chunks

class ManimDocPipeline:
    """
    Complete pipeline for processing Manim HTML documentation 
    and creating ChromaDB vector database
    """
    
    def __init__(self, html_directory: str, db_path: str = "./manim_chromadb", 
                 collection_name: str = "manim_docs"):
        """
        Initialize the pipeline
        
        Args:
            html_directory: Root directory containing HTML files
            db_path: Path where ChromaDB will be stored
            collection_name: Name of the ChromaDB collection
        """
        self.html_directory = Path(html_directory)
        self.db_path = db_path
        self.collection_name = collection_name
        
        self.parser = ManimHTMLParser()
        self.vectorizer = ManimDocVectorizer()
        
        # Statistics
        self.stats = {
            'total_files': 0,
            'successful_parses': 0,
            'failed_parses': 0,
            'total_chunks': 0
        }
        
        # Initialize ChromaDB
        self.client = None
        self.collection = None
        
    def initialize_chromadb(self, reset: bool = False):
        """Initialize ChromaDB client and collection"""
        print(f"Initializing ChromaDB at {self.db_path}...")
        
        # Create client
        self.client = chromadb.PersistentClient(path=self.db_path)
        
        # Reset if requested
        if reset:
            try:
                self.client.delete_collection(name=self.collection_name)
                print(f"Deleted existing collection: {self.collection_name}")
            except:
                pass
        
        # Create or get collection
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"description": "Manim Community Documentation"}
        )
        
        print(f"Collection '{self.collection_name}' ready.")
        
    def find_html_files(self) -> List[Path]:
        """Recursively find all HTML files in the directory"""
        html_files = []
        
        print(f"Scanning directory: {self.html_directory}")
        print(f"Directory exists: {self.html_directory.exists()}")
        print(f"Is directory: {self.html_directory.is_dir()}")
        
        if not self.html_directory.exists():
            print(f"ERROR: Directory does not exist: {self.html_directory}")
            return html_files
        
        if not self.html_directory.is_dir():
            print(f"ERROR: Path is not a directory: {self.html_directory}")
            return html_files
        
        # List contents of directory
        try:
            contents = list(self.html_directory.iterdir())
            print(f"Directory contains {len(contents)} items")
            print(f"First few items: {[item.name for item in contents[:5]]}")
        except Exception as e:
            print(f"Error listing directory contents: {e}")
            return html_files
        
        # Walk through directory
        file_count = 0
        dir_count = 0
        
        for root, dirs, files in os.walk(self.html_directory):
            dir_count += len(dirs)
            for file in files:
                file_count += 1
                if file.endswith('.html') or file.endswith('.htm'):
                    html_files.append(Path(root) / file)
        
        print(f"Scanned {dir_count} directories and {file_count} files")
        print(f"Found {len(html_files)} HTML files")
        
        if len(html_files) == 0 and file_count > 0:
            print("\nWARNING: Found files but no HTML files. Checking file extensions...")
            extensions = set()
            for root, dirs, files in os.walk(self.html_directory):
                for file in files[:20]:  # Check first 20 files
                    ext = Path(file).suffix
                    if ext:
                        extensions.add(ext)
            print(f"File extensions found: {extensions}")
        
        return html_files
    
    def process_html_file(self, html_path: Path) -> Optional[List[Dict[str, Any]]]:
        """Process a single HTML file and return chunks"""
        try:
            # Create relative path for URL
            rel_path = html_path.relative_to(self.html_directory)
            doc_url = str(rel_path)
            
            # Parse HTML
            entry = self.parser.parse_file(str(html_path))
            
            if entry is None:
                return None
            
            # Update URL
            entry.doc_url = doc_url
            
            # Create chunks
            chunks = self.vectorizer.create_chunks(entry)
            
            return chunks
            
        except Exception as e:
            print(f"Error processing {html_path}: {str(e)}")
            return None
    
    def insert_chunks(self, chunks: List[Dict[str, Any]]):
        """Insert chunks into ChromaDB"""
        if not chunks:
            return
        
        ids = [chunk['id'] for chunk in chunks]
        documents = [chunk['text'] for chunk in chunks]
        metadatas = [chunk['metadata'] for chunk in chunks]
        
        self.collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas
        )
        
        self.stats['total_chunks'] += len(chunks)
    
    def process_all(self, reset_db: bool = False):
        """Process all HTML files and populate ChromaDB"""
        # Initialize database
        self.initialize_chromadb(reset=reset_db)
        
        # Find all HTML files
        html_files = self.find_html_files()
        self.stats['total_files'] = len(html_files)
        
        # Process each file
        print("\nProcessing HTML files...")
        for html_file in tqdm(html_files, desc="Processing"):
            chunks = self.process_html_file(html_file)
            
            if chunks:
                self.insert_chunks(chunks)
                self.stats['successful_parses'] += 1
            else:
                self.stats['failed_parses'] += 1
        
        print("\nProcessing complete!")
    
    def query(self, query_text: str, n_results: int = 5, 
              category_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Query the ChromaDB for relevant documentation
        
        Args:
            query_text: The search query
            n_results: Number of results to return
            category_filter: Optional category to filter by (e.g., 'animation', 'mobject')
            
        Returns:
            List of results with metadata
        """
        if self.collection is None:
            self.initialize_chromadb()
        
        # Build where clause for filtering
        where = None
        if category_filter:
            where = {"category": category_filter}
        
        # Query ChromaDB
        results = self.collection.query(
            query_texts=[query_text],
            n_results=n_results,
            where=where
        )
        
        # Format results
        formatted_results = []
        for i in range(len(results['ids'][0])):
            formatted_results.append({
                'id': results['ids'][0][i],
                'text': results['documents'][0][i],
                'distance': results['distances'][0][i],
                'class_name': results['metadatas'][0][i].get('class_name', 'Unknown'),
                'qualified_name': results['metadatas'][0][i].get('qualified_name', 'Unknown'),
                'category': results['metadatas'][0][i].get('category', 'Unknown'),
                'type': results['metadatas'][0][i].get('type', 'Unknown'),
                'url': results['metadatas'][0][i].get('url', '')
            })
        
        return formatted_results
    
    def get_statistics(self) -> Dict[str, int]:
        """Get processing statistics"""
        return self.stats.copy()
    
    def get_collection_info(self) -> Dict[str, Any]:
        """Get information about the ChromaDB collection"""
        if self.collection is None:
            self.initialize_chromadb()
        
        return {
            'name': self.collection_name,
            'count': self.collection.count(),
            'metadata': self.collection.metadata
        }

# Example usage
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Parse Manim HTML documentation and create ChromaDB')
    parser.add_argument('html_dir', type=str, help='Directory containing Manim HTML documentation')
    parser.add_argument('--db-path', type=str, default='./manim_chromadb', 
                       help='Path to store ChromaDB (default: ./manim_chromadb)')
    parser.add_argument('--collection-name', type=str, default='manim_docs',
                       help='ChromaDB collection name (default: manim_docs)')
    parser.add_argument('--reset', action='store_true',
                       help='Reset/recreate the database if it exists')
    
    args = parser.parse_args()
    
    # Verify directory exists
    html_dir_path = Path(args.html_dir)
    if not html_dir_path.exists():
        print(f"ERROR: Directory does not exist: {args.html_dir}")
        exit(1)
    
    if not html_dir_path.is_dir():
        print(f"ERROR: Path is not a directory: {args.html_dir}")
        exit(1)
    
    print(f"Processing directory: {html_dir_path.absolute()}")
    
    # Create pipeline and process
    pipeline = ManimDocPipeline(
        html_directory=args.html_dir,
        db_path=args.db_path,
        collection_name=args.collection_name
    )
    
    pipeline.process_all(reset_db=args.reset)
    
    # Print statistics
    stats = pipeline.get_statistics()
    print("\n" + "="*80)
    print("Processing Complete!")
    print("="*80)
    print(f"Total HTML files processed: {stats['total_files']}")
    print(f"Successful parses: {stats['successful_parses']}")
    print(f"Failed parses: {stats['failed_parses']}")
    print(f"Total chunks created: {stats['total_chunks']}")
    print(f"Database path: {args.db_path}")
    print(f"Collection name: {args.collection_name}")
    
    # Only run example query if we have data
    if stats['total_chunks'] > 0:
        print("\n" + "="*80)
        print("Example Query Test")
        print("="*80)
        results = pipeline.query("How to create animations with complex functions?", n_results=3)
        
        for i, result in enumerate(results, 1):
            print(f"\n{i}. {result['class_name']}")
            print(f"   Category: {result['category']}")
            print(f"   Distance: {result['distance']:.4f}")
            print(f"   Preview: {result['text'][:150]}...")
    else:
        print("\nNo data to query. Please check the directory path and try again.")
