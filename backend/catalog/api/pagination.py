from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    """Page-number pagination: default 25, maximum 200 (section 9)."""

    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 200
