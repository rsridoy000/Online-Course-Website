def get_client_ip(request):
    """
    Safely retrieves the client IP address.
    Checks HTTP_X_FORWARDED_FOR header first, then REMOTE_ADDR.
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')
