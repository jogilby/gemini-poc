class DocumentRecord:
    def __init__(self, file_id: str, file_name: str, project_id: int, source_url: str, source_page: int):        
        self.file_id = file_id
        self.file_name = file_name
        self.project_id = project_id
        self.source_url = source_url
        self.source_page = source_page
        self.chunks = []

    @property
    def file_id(self):
        return self._file_id

    @file_id.setter
    def file_id(self, value):
        self._file_id = value

    @property
    def file_name(self):
        return self._file_name

    @file_name.setter
    def file_name(self, value):
        self._file_name = value

    @property
    def project_id(self):
        return self._project_id

    @project_id.setter
    def project_id(self, value):
        self._project_id = value

    @property
    def source_url(self):
        return self._source_url

    @source_url.setter
    def source_url(self, value):
        self._source_url = value

    @property
    def source_page(self):
        return self._source_page

    @source_page.setter
    def source_page(self, value):
        self._source_page = value

    def add(self, item):
        self.chunks.append(item)

    def __iter__(self):
        return iter(self.chunks)
    
    def __len__(self):
        return len(self.chunks)

