package { 'python27':
    ensure      => installed,
    name        => 'Python 2.7.8',
    provider    => 'windows',
    source      => 'https://www.python.org/ftp/python/2.7.8/python-2.7.8.amd64.msi',
}

package { 'python33':
    ensure      => installed,
    name        => 'Python 3.3.5',
    provider    => 'windows',
    source      => 'https://www.python.org/ftp/python/3.3.5/python-3.3.5.amd64.msi',
}

package { 'python34':
    ensure      => installed,
    name        => 'Python 3.4.1',
    provider    => 'windows',
    source      => 'https://www.python.org/ftp/python/3.4.1/python-3.4.1.amd64.msi',
}

file { 'get-pip.py':
    path    => 'C:\tmp\get-pip.py',
    ensure  => file,
    source  => 'C:\cygwin64\vagrant\puppet\get-pip.py',
    source_permissions  => ignore,
}

exec { 'pip27':
    command => 'C:\Python27\python.exe C:\tmp\get-pip.py',
    require => [
        Package['python27'],
        File['get-pip.py'],
    ]
}

exec { 'tox':
    command => 'C:\Python27\Scripts\pip.exe install tox',
    require => Exec['pip27'],
}
