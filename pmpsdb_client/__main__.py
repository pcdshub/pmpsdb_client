from .cli import create_parser, main

main(create_parser().parse_args())
