// Kamus komponen: alias teks bebas → identitas baku yang dipakai pencocokan CVE.
//
// - `cpe`  : pasangan "vendor:produk" CPE 2.3 NVD (yang pertama = utama; sisanya nama lama/alternatif yang
//            juga dipakai NVD, mis. nginx dulu `nginx:nginx`, kini `f5:nginx`). Kosong = cocokkan lewat purl saja.
// - `bagian`: 'a' aplikasi | 'o' sistem operasi (segmen `part` CPE).
// - `purl` : basis Package URL untuk OSV/GitHub Advisory (tanpa versi), mis. "pkg:npm/jquery".
// - `alias`: ditulis huruf kecil; dicocokkan per kata utuh, alias terpanjang menang
//            (mis. "apache tomcat" mengalahkan "apache").
//
// Tambahkan entri di sini bila produk yang sering dipakai satuan belum dikenali (lihat komponen ber-vendor NULL).

export const KAMUS_KOMPONEN = [
  // --- Server web / proxy
  { nama: 'nginx', cpe: ['f5:nginx', 'nginx:nginx'], alias: ['nginx', 'engine-x', 'engine x'] },
  { nama: 'Apache HTTP Server', cpe: ['apache:http_server'], alias: ['apache', 'apache2', 'httpd', 'apache httpd', 'apache http server'] },
  { nama: 'Apache Tomcat', cpe: ['apache:tomcat'], alias: ['tomcat', 'apache tomcat'] },
  { nama: 'Microsoft IIS', cpe: ['microsoft:internet_information_services'], alias: ['iis', 'microsoft-iis', 'microsoft iis'] },
  { nama: 'LiteSpeed Web Server', cpe: ['litespeedtech:litespeed_web_server'], alias: ['litespeed', 'openlitespeed'] },
  { nama: 'OpenResty', cpe: ['openresty:openresty'], alias: ['openresty'] },
  { nama: 'Caddy', cpe: ['caddyserver:caddy'], alias: ['caddy'] },
  { nama: 'HAProxy', cpe: ['haproxy:haproxy'], alias: ['haproxy'] },
  { nama: 'Traefik', cpe: ['traefik:traefik'], alias: ['traefik'] },
  { nama: 'Eclipse Jetty', cpe: ['eclipse:jetty'], alias: ['jetty'] },
  { nama: 'WildFly', cpe: ['redhat:wildfly'], alias: ['wildfly'] },
  { nama: 'Gunicorn', cpe: ['gunicorn:gunicorn'], alias: ['gunicorn'] },
  { nama: 'OpenSSL', cpe: ['openssl:openssl'], alias: ['openssl'] },

  // --- Bahasa & runtime
  { nama: 'PHP', cpe: ['php:php'], alias: ['php', 'php-fpm'] },
  { nama: 'Node.js', cpe: ['nodejs:node.js'], alias: ['node', 'nodejs', 'node.js', 'node js'] },
  { nama: 'Go', cpe: ['golang:go'], alias: ['golang', 'go'] },
  { nama: 'Python', cpe: ['python:python'], alias: ['python', 'python3'] },
  { nama: 'Java', cpe: ['oracle:jdk', 'oracle:openjdk'], alias: ['java', 'jdk', 'openjdk'] },
  { nama: '.NET', cpe: ['microsoft:.net'], alias: ['.net', 'dotnet', '.net core'] },
  { nama: '.NET Framework', cpe: ['microsoft:.net_framework'], alias: ['.net framework', 'dotnet framework'] },

  // --- Framework backend / CMS
  { nama: 'Laravel', cpe: ['laravel:framework'], purl: 'pkg:composer/laravel/framework', alias: ['laravel'] },
  { nama: 'CodeIgniter', cpe: ['codeigniter:codeigniter4', 'codeigniter:codeigniter'], alias: ['codeigniter', 'code igniter', 'ci4'] },
  { nama: 'Symfony', cpe: ['symfony:symfony', 'sensiolabs:symfony'], purl: 'pkg:composer/symfony/symfony', alias: ['symfony'] },
  { nama: 'Yii', cpe: ['yiiframework:yii'], alias: ['yii', 'yii2'] },
  { nama: 'WordPress', cpe: ['wordpress:wordpress'], alias: ['wordpress', 'wp'] },
  { nama: 'Drupal', cpe: ['drupal:drupal'], alias: ['drupal'] },
  { nama: 'Moodle', cpe: ['moodle:moodle'], alias: ['moodle'] },
  { nama: 'phpMyAdmin', cpe: ['phpmyadmin:phpmyadmin'], alias: ['phpmyadmin'] },
  { nama: 'Django', cpe: ['djangoproject:django'], purl: 'pkg:pypi/django', alias: ['django'] },
  { nama: 'Flask', cpe: ['palletsprojects:flask'], purl: 'pkg:pypi/flask', alias: ['flask'] },
  { nama: 'FastAPI', cpe: ['tiangolo:fastapi'], purl: 'pkg:pypi/fastapi', alias: ['fastapi'] },
  { nama: 'Express', cpe: ['expressjs:express', 'openjsf:express'], purl: 'pkg:npm/express', alias: ['express', 'expressjs', 'express.js'] },
  { nama: 'NestJS', purl: 'pkg:npm/@nestjs/core', alias: ['nestjs', 'nest.js', 'nest js'] },
  { nama: 'Next.js', cpe: ['vercel:next.js'], purl: 'pkg:npm/next', alias: ['next.js', 'nextjs', 'next js'] },
  { nama: 'Nuxt', cpe: ['nuxt:nuxt'], purl: 'pkg:npm/nuxt', alias: ['nuxt', 'nuxt.js', 'nuxtjs'] },
  { nama: 'Spring Boot', cpe: ['vmware:spring_boot'], purl: 'pkg:maven/org.springframework.boot/spring-boot', alias: ['spring boot', 'springboot'] },
  { nama: 'Spring Framework', cpe: ['vmware:spring_framework', 'pivotal_software:spring_framework'], purl: 'pkg:maven/org.springframework/spring-core', alias: ['spring', 'spring framework', 'spring mvc'] },
  { nama: 'Apache Struts', cpe: ['apache:struts'], alias: ['struts', 'apache struts', 'struts2'] },
  { nama: 'Ruby on Rails', cpe: ['rubyonrails:rails'], purl: 'pkg:gem/rails', alias: ['rails', 'ruby on rails', 'ror'] },
  { nama: 'ASP.NET Core', cpe: ['microsoft:asp.net_core'], alias: ['asp.net core', 'aspnet core', 'asp.net'] },
  { nama: 'Gin', cpe: ['gin-gonic:gin'], purl: 'pkg:golang/github.com/gin-gonic/gin', alias: ['gin', 'gin-gonic'] },
  { nama: 'Keycloak', cpe: ['redhat:keycloak'], alias: ['keycloak'] },
  { nama: 'Grafana', cpe: ['grafana:grafana'], alias: ['grafana'] },

  // --- Frontend
  { nama: 'React', cpe: ['facebook:react'], purl: 'pkg:npm/react', alias: ['react', 'reactjs', 'react.js'] },
  { nama: 'Vue.js', cpe: ['vuejs:vue.js'], purl: 'pkg:npm/vue', alias: ['vue', 'vuejs', 'vue.js'] },
  { nama: 'Angular', purl: 'pkg:npm/@angular/core', alias: ['angular'] },
  { nama: 'AngularJS', cpe: ['angularjs:angular.js'], purl: 'pkg:npm/angular', alias: ['angularjs', 'angular.js', 'angular js'] },
  { nama: 'Svelte', cpe: ['svelte:svelte'], purl: 'pkg:npm/svelte', alias: ['svelte'] },
  { nama: 'SvelteKit', purl: 'pkg:npm/@sveltejs/kit', alias: ['sveltekit', 'svelte kit'] },
  { nama: 'jQuery', cpe: ['jquery:jquery'], purl: 'pkg:npm/jquery', alias: ['jquery'] },
  { nama: 'Bootstrap', cpe: ['getbootstrap:bootstrap'], purl: 'pkg:npm/bootstrap', alias: ['bootstrap'] },
  { nama: 'Lodash', cpe: ['lodash:lodash'], purl: 'pkg:npm/lodash', alias: ['lodash'] },
  { nama: 'Moment.js', cpe: ['momentjs:moment'], purl: 'pkg:npm/moment', alias: ['moment', 'moment.js', 'momentjs'] },

  // --- Basis data & penyimpanan
  { nama: 'MySQL', cpe: ['oracle:mysql', 'oracle:mysql_server'], alias: ['mysql', 'mysql server'] },
  { nama: 'MariaDB', cpe: ['mariadb:mariadb'], alias: ['mariadb'] },
  { nama: 'PostgreSQL', cpe: ['postgresql:postgresql'], alias: ['postgresql', 'postgres', 'psql', 'pgsql'] },
  { nama: 'MongoDB', cpe: ['mongodb:mongodb'], alias: ['mongodb', 'mongo'] },
  { nama: 'Redis', cpe: ['redis:redis'], alias: ['redis'] },
  { nama: 'Microsoft SQL Server', cpe: ['microsoft:sql_server'], alias: ['sql server', 'mssql', 'ms sql', 'microsoft sql server'] },
  { nama: 'Oracle Database', cpe: ['oracle:database_server'], alias: ['oracle', 'oracle db', 'oracle database'] },
  { nama: 'Elasticsearch', cpe: ['elastic:elasticsearch'], alias: ['elasticsearch', 'elastic search'] },

  // --- Sistem operasi
  { nama: 'Ubuntu', cpe: ['canonical:ubuntu_linux'], bagian: 'o', alias: ['ubuntu'] },
  { nama: 'Debian', cpe: ['debian:debian_linux'], bagian: 'o', alias: ['debian'] },
  { nama: 'CentOS', cpe: ['centos:centos'], bagian: 'o', alias: ['centos'] },
  { nama: 'Red Hat Enterprise Linux', cpe: ['redhat:enterprise_linux'], bagian: 'o', alias: ['rhel', 'red hat', 'redhat', 'red hat enterprise linux'] },
];
